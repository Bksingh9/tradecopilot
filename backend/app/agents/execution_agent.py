"""Execution agent.

Behavior depends on autonomy mode:
- ADVISORY:   never places orders — returns 'proposed' with a draft OrderRequest.
- SEMI_AUTO:  places approved candidates if a single-trade open-position guard passes
              (e.g. one open position per symbol).
- FULL_AUTO:  places approved candidates without per-call confirmation,
              gated by paper qualification + explicit consent (checked at the
              orchestrator level before this agent is invoked).

Also exposes:
- `flatten_eod(session, user)` — close every OPEN trade for symbols whose
  exchange has reached its session close.
- `manage_open_trades(session, user)` — close on stop-hit / target-hit / time-stop
  using the most recent quote.
"""
from __future__ import annotations

from datetime import datetime, time, timezone, timedelta
from typing import Iterable, Optional

from sqlmodel import Session, select

from app.agents.models import AutonomyMode, CandidateTrade, ExecutionResult, RiskDecision
from app.audit import service as audit
from app.auth.models import User
from app.brokers.models import OrderRequest
from app.common.exceptions import BrokerError, NotFound, RiskRuleViolation
from app.common.logging import get_logger
from app.data import get_realtime_quote
from app.trading import execution as exec_mod
from app.trading.models import Trade

logger = get_logger(__name__)


# Approximate exchange close times (UTC); adjust per holiday calendar in prod.
_EXCHANGE_CLOSE_UTC = {
    "NSE": time(10, 0),    # 15:30 IST = 10:00 UTC
    "BSE": time(10, 0),
    "US": time(20, 0),     # 16:00 ET ≈ 20:00 UTC (handles DST roughly)
}


class ExecutionAgent:
    def run(
        self,
        session: Session,
        decision: RiskDecision,
        user: User,
        mode: AutonomyMode,
        broker: str = "alpaca",
    ) -> ExecutionResult:
        if decision.action == "reject":
            audit.record(
                session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
                action="agent.execution.skipped",
                subject_type="candidate", subject_id=decision.candidate.symbol,
                payload={"reason": decision.reason, "side": decision.candidate.side},
            )
            return ExecutionResult(
                candidate=decision.candidate, decision=decision,
                status="skipped", error=decision.reason,
            )

        cand = decision.candidate
        order = OrderRequest(
            symbol=cand.symbol,
            exchange=cand.exchange,
            side=cand.side,
            qty=decision.final_qty,
            order_type="MARKET",
            price=cand.entry,
            stop_price=cand.stop,
            strategy=cand.strategy,
            paper=cand.paper,
        )

        if mode == "advisory":
            audit.record(
                session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
                action="agent.execution.proposed",
                subject_type="candidate", subject_id=cand.symbol,
                payload={"side": cand.side, "qty": order.qty, "strategy": cand.strategy},
            )
            return ExecutionResult(
                candidate=cand, decision=decision, status="proposed",
            )

        if mode == "semi_auto" and self._has_open_in_symbol(session, user, cand.symbol):
            audit.record(
                session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
                action="agent.execution.skipped",
                subject_type="candidate", subject_id=cand.symbol,
                payload={"reason": "semi_auto: one-open-per-symbol guard"},
            )
            return ExecutionResult(
                candidate=cand, decision=decision, status="skipped",
                error="semi_auto: already have an open position in this symbol",
            )

        try:
            res = exec_mod.execute_order(
                session, user.id, user.tenant_id, broker, order, paper=cand.paper
            )
        except (RiskRuleViolation, BrokerError, NotFound) as e:
            audit.record(
                session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
                action="agent.execution.blocked",
                subject_type="candidate", subject_id=cand.symbol,
                payload={"error": str(e)[:200]},
            )
            return ExecutionResult(
                candidate=cand, decision=decision, status="blocked", error=str(e)[:300],
            )

        audit.record(
            session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
            action="agent.execution.placed",
            subject_type="order", subject_id=res.broker_order_id,
            payload={"side": cand.side, "qty": order.qty, "broker": broker, "strategy": cand.strategy},
        )
        return ExecutionResult(
            candidate=cand, decision=decision, status="placed",
            broker_order_id=res.broker_order_id,
        )

    # --- Maintenance ----------------------------------------------------------
    def manage_open_trades(self, session: Session, user: User) -> list[ExecutionResult]:
        """Close trades whose stop/target was hit, or that exceeded time-stop."""
        now = datetime.utcnow()
        out: list[ExecutionResult] = []
        for t in self._open_trades(session, user):
            close_reason: Optional[str] = None
            close_price: Optional[float] = None
            try:
                q = get_realtime_quote(t.symbol, exchange_hint=t.exchange)
                last = q.ltp
                # stop / target
                if t.side == "BUY":
                    if t.stop_price and last <= t.stop_price:
                        close_reason, close_price = "stop_hit", float(last)
                    elif t.target_price and last >= t.target_price:
                        close_reason, close_price = "target_hit", float(last)
                else:
                    if t.stop_price and last >= t.stop_price:
                        close_reason, close_price = "stop_hit", float(last)
                    elif t.target_price and last <= t.target_price:
                        close_reason, close_price = "target_hit", float(last)
            except Exception:
                pass

            # time-stop: 5d for swing; tighten in prod with strategy config.
            if not close_reason and t.opened_at and (now - t.opened_at) > timedelta(days=5):
                close_reason = "time_stop"

            if close_reason and close_price is None:
                # we couldn't price it — leave open
                continue

            if close_reason:
                self._close_trade(session, user, t, close_reason, close_price)
                out.append(ExecutionResult(
                    candidate=CandidateTrade(
                        symbol=t.symbol, exchange=t.exchange, side=t.side,
                        qty=t.qty, entry=t.entry_price, stop=t.stop_price or 0.0,
                        target=t.target_price, strategy=t.strategy or "",
                        rationale=close_reason, paper=t.paper,
                    ),
                    decision=RiskDecision(
                        candidate=CandidateTrade(
                            symbol=t.symbol, side=t.side, qty=t.qty, entry=t.entry_price,
                            stop=t.stop_price or 0.0, strategy=t.strategy or "",
                            rationale=close_reason,
                        ),
                        action="approve", final_qty=t.qty, reason=close_reason,
                    ),
                    status="placed",
                ))
        return out

    def flatten_eod(self, session: Session, user: User) -> list[ExecutionResult]:
        """Close every open trade for an exchange that has hit its session close."""
        now_utc = datetime.now(timezone.utc).timetz().replace(tzinfo=None)
        out: list[ExecutionResult] = []
        for t in self._open_trades(session, user):
            close_t = _EXCHANGE_CLOSE_UTC.get((t.exchange or "").upper())
            if close_t is None or now_utc < close_t:
                continue
            try:
                q = get_realtime_quote(t.symbol, exchange_hint=t.exchange)
                price = float(q.ltp)
            except Exception:
                price = float(t.entry_price)
            self._close_trade(session, user, t, "eod_flatten", price)
            out.append(ExecutionResult(
                candidate=CandidateTrade(
                    symbol=t.symbol, side=t.side, qty=t.qty, entry=t.entry_price,
                    stop=t.stop_price or 0.0, strategy=t.strategy or "",
                    rationale="eod_flatten",
                ),
                decision=RiskDecision(
                    candidate=CandidateTrade(
                        symbol=t.symbol, side=t.side, qty=t.qty, entry=t.entry_price,
                        stop=t.stop_price or 0.0, strategy=t.strategy or "",
                        rationale="eod_flatten",
                    ),
                    action="approve", final_qty=t.qty, reason="eod_flatten",
                ),
                status="placed",
            ))
        return out

    # --- Helpers --------------------------------------------------------------
    @staticmethod
    def _open_trades(session: Session, user: User) -> Iterable[Trade]:
        return session.exec(
            select(Trade).where(
                Trade.user_id == user.id,
                Trade.tenant_id == user.tenant_id,
                Trade.status == "OPEN",
            )
        ).all()

    @staticmethod
    def _has_open_in_symbol(session: Session, user: User, symbol: str) -> bool:
        return any(t.symbol == symbol for t in ExecutionAgent._open_trades(session, user))

    @staticmethod
    def _close_trade(session: Session, user: User, t: Trade, reason: str, exit_price: float) -> None:
        sign = 1 if t.side == "BUY" else -1
        pnl = (exit_price - t.entry_price) * sign * t.qty
        risk_per_share = max(abs(t.entry_price - (t.stop_price or t.entry_price)), 1e-9)
        r = (exit_price - t.entry_price) * sign / risk_per_share
        t.exit_price = exit_price
        t.realized_pnl = float(pnl)
        t.r_multiple = float(r)
        t.status = "CLOSED"
        t.closed_at = datetime.utcnow()
        session.add(t)
        session.commit()
        audit.record(
            session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
            action="agent.execution.closed",
            subject_type="trade", subject_id=t.id,
            payload={"reason": reason, "pnl": float(pnl), "r": float(r)},
        )

        # Best-effort vector hook so the user's history is searchable.
        try:
            from app.vector_memory import text_embedding_stub, upsert_user_trade
            blob = (
                f"{t.symbol} {t.side} qty={t.qty} entry={t.entry_price} exit={exit_price} "
                f"pnl={pnl:.2f} r={r:.2f} strategy={t.strategy or ''} reason={reason}"
            )
            upsert_user_trade(
                tenant_id=user.tenant_id, user_id=user.id, trade_id=t.id,
                vector=text_embedding_stub(blob),
                meta={"symbol": t.symbol, "side": t.side, "pnl": float(pnl), "r": float(r),
                      "strategy": t.strategy, "reason": reason},
            )
        except Exception:
            pass
