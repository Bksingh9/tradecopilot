"""Process-wide APScheduler instance + auto-cycle + ML retrain jobs."""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.common.logging import get_logger

_scheduler: BackgroundScheduler | None = None
logger = get_logger(__name__)


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.start()
        _register_periodic_jobs(_scheduler)
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


# ---------------------------------------------------------------------------
# Periodic jobs
# ---------------------------------------------------------------------------
def _register_periodic_jobs(scheduler: BackgroundScheduler) -> None:
    """Set up the auto-trade cycle + ML retrain jobs.

    - auto_trade_cycle: every 15 minutes, run the agent cycle for every user
      whose autonomy_mode is `semi_auto` or `full_auto` over their watchlist.
      The orchestrator itself respects the user's autonomy: in `semi_auto` it
      generates StrategyTuningSuggestions and signals but does NOT auto-place
      trades; in `full_auto` it places (paper) trades through the same
      execution.evaluate_order risk gate that the manual flow uses. Hard caps
      from env still apply, kill-switch still blocks.
    - retrain_models: hourly, retrain prediction models for users who have
      hit fresh closed-trade thresholds since the last retrain.
    """
    scheduler.add_job(
        _auto_trade_cycle_job,
        trigger=IntervalTrigger(minutes=15),
        id="auto_trade_cycle",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        _retrain_due_models_job,
        trigger=IntervalTrigger(hours=1),
        id="retrain_due_models",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("scheduler.periodic_jobs registered: auto_trade_cycle (15m), retrain_due_models (1h)")


def _auto_trade_cycle_job() -> None:
    """Run agent cycle for users with autonomy>=semi_auto.

    Exceptions per-user are caught + logged so one bad user can't kill the
    sweep. Each cycle uses the user's saved watchlist; users with no
    watchlist are skipped silently.
    """
    try:
        from sqlmodel import select
        from app.agents.orchestrator import Orchestrator
        from app.auth.models import User
        from app.database import session_scope
        from app.users import service as user_service
    except Exception as e:
        logger.exception("auto_trade_cycle import failed: %s", e)
        return

    orch = Orchestrator()
    try:
        with session_scope() as session:
            users = session.exec(
                select(User).where(User.autonomy_mode.in_(("semi_auto", "full_auto")))
            ).all()
    except Exception as e:
        logger.exception("auto_trade_cycle session failed: %s", e)
        return

    if not users:
        return

    for u in users:
        try:
            with session_scope() as session:
                prefs = user_service.get_or_create_prefs(session, u)
                symbols = list(prefs.watchlist or [])
                if not symbols:
                    continue
                orch.run_cycle(
                    session, u, symbols,
                    timeframe="1d", broker="zerodha", exchange_hint="NSE",
                )
                logger.info("auto_cycle ok user=%s symbols=%d", u.id, len(symbols))
        except Exception as e:
            logger.warning("auto_cycle failed user=%s: %s", u.id, e)


def _retrain_due_models_job() -> None:
    """Trigger ML model retraining for users who hit fresh closed-trade thresholds.

    Naïve heuristic: every user with ≥20 closed paper trades total, retrain
    their personalised model once per session. A production-grade version
    would track a `last_trained_at` timestamp on the model registry; for now
    we just log + call train_model with default config.
    """
    try:
        from sqlmodel import func, select
        from app.auth.models import User
        from app.database import session_scope
        from app.prediction_service.training import train_model, ModelConfig
        from app.trading.models import Trade
    except Exception as e:
        logger.exception("retrain import failed: %s", e)
        return

    try:
        with session_scope() as session:
            # users with ≥20 closed trades
            counts = session.exec(
                select(Trade.user_id, func.count(Trade.id))
                .where(Trade.status == "CLOSED")
                .group_by(Trade.user_id)
            ).all()
            due_user_ids = [uid for uid, n in counts if n and n >= 20]
    except Exception as e:
        logger.exception("retrain count query failed: %s", e)
        return

    if not due_user_ids:
        return

    logger.info("retrain due for %d user(s): %s", len(due_user_ids), due_user_ids[:5])
    # Train default model config (symbol-agnostic baseline). A per-user model
    # personalisation would key on user_id + their most-traded symbols.
    try:
        cfg = ModelConfig(symbol="RELIANCE.NS", timeframe="1d")  # baseline
        result = train_model(cfg)
        logger.info("retrain result: %s", result)
    except Exception as e:
        logger.warning("retrain failed: %s", e)


# ---------------------------------------------------------------------------
# Helpers used elsewhere (e.g. close_position calls schedule_retrain_if_due)
# ---------------------------------------------------------------------------
def schedule_retrain_if_due(user_id: int, closed_trade_count: int) -> None:
    """Inline post-close hook: if user just crossed a 20-trade boundary,
    schedule a one-shot retrain job for ASAP.

    Idempotent: APScheduler dedupes by job id within the same boundary.
    """
    if closed_trade_count == 0 or closed_trade_count % 20 != 0:
        return
    sched = get_scheduler()
    job_id = f"retrain_user_{user_id}_at_{closed_trade_count}"
    try:
        sched.add_job(
            _retrain_due_models_job,
            id=job_id,
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info("retrain scheduled job_id=%s", job_id)
    except Exception as e:
        logger.warning("retrain schedule failed for user=%s: %s", user_id, e)
