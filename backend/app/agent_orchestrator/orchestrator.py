"""ML + RAG-aware decision cycle.

Per (user, symbol):
  1) data_ingestion → recent_window
  2) prediction_service.get_prediction
  3) rag_context.build_market_context (similar windows + textual snippets)
  4) Build DecisionContext (with user_behavior_profile)
  5) Existing StrategyAgent.propose, RiskAgent.review, ExecutionAgent.run
     (autonomy_mode honored — same gates as the baseline orchestrator)
  6) Audit each stage, return list[DecisionOutcome]
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session

from app.agent_orchestrator.models import DecisionContext, DecisionOutcome, DecisionProposal
from app.agents.execution_agent import ExecutionAgent
from app.agents.models import AutonomyMode, CandidateTrade
from app.agents.risk_agent import RiskAgent
from app.agents.strategy import StrategyAgent
from app.audit import service as audit
from app.auth.models import User
from app.common.exceptions import PermissionDenied
from app.common.logging import get_logger
from app.data import get_ohlcv
from app.journal.analytics import get_user_behavior_profile
from app.rag_context import build_market_context
from app.trading import risk as risk_mod
from app.trading.models import RiskRule

logger = get_logger(__name__)


def _risk_snapshot(session: Session, user: User) -> dict:
    rule = session.get(RiskRule, user.id) or RiskRule(user_id=user.id, tenant_id=user.tenant_id)
    eff = risk_mod.effective_rule(rule)
    return {
        "max_risk_per_trade_pct": eff.max_risk_per_trade_pct,
        "daily_loss_limit_pct": eff.daily_loss_limit_pct,
        "max_open_positions": eff.max_open_positions,
        "paper_only": eff.paper_only,
        "starting_equity": eff.starting_equity,
    }


def _load_window(symbol: str, timeframe: str, exchange_hint: Optional[str], days: int = 220):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return get_ohlcv(symbol, start, end, timeframe, exchange_hint=exchange_hint)


def _bias_candidate(cand: CandidateTrade, p_up: float) -> Optional[CandidateTrade]:
    """Drop candidates whose direction disagrees with the ML signal at high confidence."""
    if p_up >= 0.65 and cand.side == "SELL":
        return None
    if p_up <= 0.35 and cand.side == "BUY":
        return None
    return cand


def run_decision_cycle(
    session: Session,
    user: User,
    symbols: list[str],
    *,
    mode: Optional[AutonomyMode] = None,
    broker: str = "alpaca",
    timeframe: str = "1d",
    exchange_hint: Optional[str] = None,
) -> list[DecisionOutcome]:
    effective_mode: AutonomyMode = mode or user.autonomy_mode  # type: ignore[assignment]
    if effective_mode == "full_auto":
        if not user.paper_qualified_at:
            raise PermissionDenied("full_auto requires paper qualification")
        if not user.consent_full_auto:
            raise PermissionDenied("full_auto requires explicit consent")

    audit.record(
        session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
        action="agent.decision.start",
        subject_type="cycle",
        payload={"symbols": symbols, "mode": effective_mode, "timeframe": timeframe},
    )

    strategy = StrategyAgent()
    risk = RiskAgent()
    executor = ExecutionAgent()
    outcomes: list[DecisionOutcome] = []
    profile = get_user_behavior_profile(session, user)

    for sym in symbols:
        try:
            window = _load_window(sym, timeframe, exchange_hint)
            ctx_dict = build_market_context(
                tenant_id=user.tenant_id, symbol=sym, timeframe=timeframe,
                recent_window=window, exchange_hint=exchange_hint,
            )
        except Exception as e:
            logger.warning("decision cycle: context build failed for %s: %s", sym, e)
            continue

        from app.prediction_service.models import PredictionResult
        prediction = PredictionResult(**ctx_dict["prediction"])

        ctx = DecisionContext(
            symbol=sym,
            timeframe=timeframe,
            prediction=prediction,
            similar_windows=ctx_dict.get("similar_windows", []),
            current_features=ctx_dict.get("current_features", {}),
            risk_snapshot=_risk_snapshot(session, user),
            autonomy=effective_mode,
            user_behavior_profile=profile,
        )

        # Build a synthetic AnalystSignal for the existing StrategyAgent.
        # We give it the regime-hint logic the baseline analyst would emit.
        from app.agents.analyst import AnalystAgent
        from app.agents.models import AnalystSignal

        signal = AnalystSignal(
            symbol=sym,
            exchange=(exchange_hint or "").upper() or None,
            timeframe=timeframe,
            timestamp=datetime.utcnow(),
            features=ctx.current_features,
            p_up=prediction.prob_up,
            regime=AnalystAgent._regime_hint(ctx.current_features),
            sentiment=0.0,
        )

        cands = strategy.propose(signal, user)
        cands = [c for c in (_bias_candidate(c, prediction.prob_up) for c in cands) if c]
        audit.record(
            session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
            action="agent.decision.propose",
            subject_type="symbol", subject_id=sym,
            payload={"n": len(cands), "p_up": prediction.prob_up,
                     "model_version": prediction.model_version},
        )

        if not cands:
            outcomes.append(DecisionOutcome(context=ctx))
            continue

        for cand in cands:
            ml_conf = float(abs(prediction.prob_up - 0.5) * 2.0)
            proposal = DecisionProposal(
                candidate=cand, ml_confidence=ml_conf,
                rationale=f"{cand.rationale} | ML p_up={prediction.prob_up:.2f} (v{prediction.model_version})",
            )
            decision = risk.review(session, cand, user)
            audit.record(
                session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
                action="agent.decision.risk",
                subject_type="symbol", subject_id=sym,
                payload={"action": decision.action, "qty": decision.final_qty},
            )

            execution = executor.run(session, decision, user, mode=effective_mode, broker=broker)
            audit.record(
                session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
                action="agent.decision.execute",
                subject_type="symbol", subject_id=sym,
                payload={"status": execution.status, "broker_order_id": execution.broker_order_id},
            )
            outcomes.append(DecisionOutcome(
                context=ctx, proposal=proposal, decision=decision, execution=execution,
            ))

    audit.record(
        session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
        action="agent.decision.end",
        subject_type="cycle",
        payload={"outcomes": len(outcomes), "mode": effective_mode},
    )
    return outcomes
