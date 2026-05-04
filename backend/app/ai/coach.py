"""AICoach: abstract boundary + a deterministic FakeCoach + Redis-queue ExternalCoach.

Production deployments run a separate worker (see app/workers/ai_worker.py)
that drains a Redis list of rendered prompts, calls the LLM service, and
posts the result back via /api/ai/callback. The backend itself never calls
any external LLM directly from this module.

If the worker / Redis / LLM are down, the backend keeps working: synchronous
endpoints fall back to FakeCoach, which returns deterministic placeholder text.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.ai.prompts import SYSTEM_PROMPT, render_trade_comment, render_tuning_review, render_weekly_report
from app.common.logging import get_logger
from app.config import settings
from app.trading.models import JournalEntry, RiskRule, Trade

logger = get_logger(__name__)


# --- Interface ---------------------------------------------------------------
class AICoach(ABC):
    @abstractmethod
    def generate_weekly_report(
        self,
        trades: list[Trade],
        journal_entries: list[JournalEntry],
        risk_config: RiskRule,
    ) -> str: ...

    @abstractmethod
    def comment_on_new_trade(self, trade: Trade, context: dict[str, Any]) -> str: ...

    def request_tuning_review(self, payload: dict, guardrails: dict) -> str:
        """Default implementation: synchronous FakeCoach response."""
        return json.dumps({
            "strategy": payload.get("strategy", "unknown"),
            "suggested_params": payload.get("current_params", {}),
            "rationale": "Placeholder — wire up an LLM worker for live tuning.",
            "disclaimer": "Educational use only. Not financial advice.",
        })


# --- Helpers -----------------------------------------------------------------
def _trade_to_safe_dict(t: Trade) -> dict:
    return {
        "id": t.id,
        "symbol": t.symbol,
        "exchange": t.exchange,
        "side": t.side,
        "qty": t.qty,
        "entry": t.entry_price,
        "exit": t.exit_price,
        "stop": t.stop_price,
        "target": t.target_price,
        "pnl": t.realized_pnl,
        "r": t.r_multiple,
        "strategy": t.strategy,
        "status": t.status,
        "opened_at": t.opened_at.isoformat() if t.opened_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
    }


def _entry_to_safe_dict(e: JournalEntry) -> dict:
    return {
        "id": e.id,
        "trade_id": e.trade_id,
        "setup": e.setup,
        "emotion": e.emotion_tag,
        "notes": (e.notes or "")[:500],
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _risk_to_safe_dict(r: RiskRule) -> dict:
    return {
        "max_risk_per_trade_pct": r.max_risk_per_trade_pct,
        "daily_loss_limit_pct": r.daily_loss_limit_pct,
        "max_open_positions": r.max_open_positions,
        "restricted_symbols": r.restricted_symbols,
        "starting_equity": r.starting_equity,
    }


def build_weekly_payload(
    trades: list[Trade],
    journal_entries: list[JournalEntry],
    risk_config: RiskRule,
) -> str:
    payload = {
        "trades": [_trade_to_safe_dict(t) for t in trades],
        "journal": [_entry_to_safe_dict(e) for e in journal_entries],
        "risk": _risk_to_safe_dict(risk_config),
    }
    return json.dumps(payload, default=str, indent=2)


# --- Fake coach (default in dev/tests) ---------------------------------------
class FakeCoach(AICoach):
    """Deterministic placeholder. Useful for tests and offline demos."""

    def generate_weekly_report(
        self,
        trades: list[Trade],
        journal_entries: list[JournalEntry],
        risk_config: RiskRule,
    ) -> str:
        payload_json = build_weekly_payload(trades, journal_entries, risk_config)
        h = hashlib.sha1(payload_json.encode()).hexdigest()[:8]
        closed = [t for t in trades if t.status == "CLOSED" and t.realized_pnl is not None]
        total_pnl = sum(t.realized_pnl or 0.0 for t in closed)
        win_rate = (
            sum(1 for t in closed if (t.realized_pnl or 0) > 0) / len(closed) * 100.0
            if closed else 0.0
        )
        return (
            f"### Snapshot (id {h})\n"
            f"- Trades: {len(trades)}, closed: {len(closed)}\n"
            f"- Total P&L: ₹{total_pnl:.2f}\n"
            f"- Win rate: {win_rate:.1f}%\n\n"
            "### What worked\n- (placeholder) Wire up an LLM worker for live coaching.\n\n"
            "### What hurt\n- (placeholder) See journal entries for emotion tags.\n\n"
            "### Process improvements\n"
            "- Stick to your daily loss limit.\n"
            "- Pre-define stops before entry.\n"
            "- Avoid trading the first 5 minutes after open.\n\n"
            "### Coach note\nTrade your plan, not your mood.\n\n"
            "Educational use only. Not financial advice."
        )

    def comment_on_new_trade(self, trade: Trade, context: dict[str, Any]) -> str:
        return (
            f"(placeholder comment for trade #{trade.id} on {trade.symbol})\n"
            "1. Setup quality: 3/5\n"
            "2. Risk hygiene: stop set; size within rule.\n"
            "3. Behavioral note: none observed.\n"
            "4. Better next time: log a 1-line thesis before entry.\n\n"
            "Educational use only. Not financial advice."
        )


# --- Redis-queue coach -------------------------------------------------------
class ExternalQueueCoach(AICoach):
    """Renders prompts and pushes them to a Redis list. The worker does the LLM call.

    For *synchronous* requests (current /weekly-report endpoint) we still return
    something useful immediately by generating a FakeCoach placeholder. The worker
    will later POST the *real* response to /api/ai/callback, which stores a fresh
    AIReport row the UI can pick up via /api/ai/reports.
    """

    def __init__(self) -> None:
        self._fallback = FakeCoach()
        self._redis_client = None

    def _redis(self):
        if self._redis_client is not None:
            return self._redis_client
        try:
            import redis as _redis
        except Exception as e:  # pragma: no cover
            logger.warning("redis library unavailable: %s", e)
            return None
        try:
            self._redis_client = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            return self._redis_client
        except Exception as e:
            logger.warning("redis connect failed: %s", e)
            self._redis_client = None
            return None

    def _enqueue(self, kind: str, prompt: str, **extra) -> bool:
        r = self._redis()
        if r is None:
            return False
        try:
            payload = json.dumps({
                "kind": kind,
                "system": SYSTEM_PROMPT,
                "user": prompt,
                **extra,
            })
            r.lpush(settings.ai_queue_name, payload)
            return True
        except Exception as e:
            logger.warning("redis lpush failed: %s", e)
            return False

    def generate_weekly_report(self, trades, journal_entries, risk_config) -> str:
        payload = build_weekly_payload(trades, journal_entries, risk_config)
        rendered = render_weekly_report(payload)
        sample_user_id = trades[0].user_id if trades else None
        sample_tenant_id = trades[0].tenant_id if trades else None
        queued = self._enqueue(
            "weekly", rendered,
            user_id=sample_user_id, tenant_id=sample_tenant_id,
        )
        # Always return something now; worker will deliver the real one async.
        if not queued:
            return self._fallback.generate_weekly_report(trades, journal_entries, risk_config)
        return self._fallback.generate_weekly_report(trades, journal_entries, risk_config) + \
            "\n\n(Live coach run queued — refresh in a minute for the real report.)"

    def comment_on_new_trade(self, trade: Trade, context: dict[str, Any]) -> str:
        rendered = render_trade_comment(
            json.dumps(_trade_to_safe_dict(trade), default=str),
            json.dumps(context, default=str),
        )
        queued = self._enqueue(
            "trade_comment", rendered,
            user_id=trade.user_id, tenant_id=trade.tenant_id, trade_id=trade.id,
        )
        if not queued:
            return self._fallback.comment_on_new_trade(trade, context)
        return self._fallback.comment_on_new_trade(trade, context) + \
            "\n\n(Live coach comment queued — refresh in a minute for the real one.)"

    def request_tuning_review(self, payload: dict, guardrails: dict) -> str:
        rendered = render_tuning_review(
            json.dumps(payload, default=str), json.dumps(guardrails, default=str)
        )
        queued = self._enqueue(
            "tuning_review", rendered,
            user_id=payload.get("user_id"),
            tenant_id=payload.get("tenant_id"),
            strategy=payload.get("strategy"),
        )
        if not queued:
            return super().request_tuning_review(payload, guardrails)
        return super().request_tuning_review(payload, guardrails)


def get_coach() -> AICoach:
    if settings.ai_coach_backend == "external":
        return ExternalQueueCoach()
    return FakeCoach()
