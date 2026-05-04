"""Risk agent — decides {approve, scale_down, reject} for each candidate.

Wraps `app.trading.risk` (hard caps + dynamic caps + kill switch). The agent
SCALES DOWN whenever the only violation is sizing/notional; it only rejects on
hard violations (restricted symbol, kill switch, daily loss limit, paper-only
gate, max open positions).
"""
from __future__ import annotations

from sqlmodel import Session

from app.agents.models import CandidateTrade, RiskDecision
from app.auth.models import User
from app.brokers.models import OrderRequest
from app.common.exceptions import RiskRuleViolation
from app.trading import risk as risk_mod
from app.trading.models import RiskRule


class RiskAgent:
    def review(
        self,
        session: Session,
        candidate: CandidateTrade,
        user: User,
    ) -> RiskDecision:
        # Kill switch first.
        blocked = risk_mod.is_blocked(session, user.id, user.tenant_id)
        if blocked:
            return RiskDecision(
                candidate=candidate, action="reject", final_qty=0,
                reason=f"kill switch: {blocked}",
            )

        rule = session.get(RiskRule, user.id) or RiskRule(
            user_id=user.id, tenant_id=user.tenant_id
        )
        ctx = risk_mod.build_context(session, user.id, rule)
        eff = risk_mod.dynamic_risk_caps(rule, ctx)

        # Volatility-aware size.
        sized_qty = risk_mod.position_size(
            equity=eff.starting_equity,
            risk_per_trade_pct=eff.max_risk_per_trade_pct,
            entry_price=candidate.entry,
            stop_price=candidate.stop,
        )

        # First try at full size; if it violates a *sizing* rule, scale down.
        order = OrderRequest(
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            side=candidate.side,
            qty=max(sized_qty, 1),
            order_type="MARKET",
            price=candidate.entry,
            stop_price=candidate.stop,
            paper=candidate.paper,
        )
        try:
            risk_mod.evaluate_order(order, rule, ctx)
            return RiskDecision(
                candidate=candidate.model_copy(update={"qty": order.qty}),
                action="approve",
                final_qty=order.qty,
                reason="ok",
                rule_snapshot=_snap(eff),
            )
        except RiskRuleViolation as e:
            msg = str(e).lower()
            if "notional" in msg or "max open positions" in msg:
                # Try to scale down.
                for divisor in (2, 4, 10):
                    smaller = max(order.qty // divisor, 0)
                    if smaller <= 0:
                        continue
                    test = order.model_copy(update={"qty": smaller})
                    try:
                        risk_mod.evaluate_order(test, rule, ctx)
                        return RiskDecision(
                            candidate=candidate.model_copy(update={"qty": smaller}),
                            action="scale_down",
                            final_qty=smaller,
                            reason=f"scaled to {smaller} (rule: {e})",
                            rule_snapshot=_snap(eff),
                        )
                    except RiskRuleViolation:
                        continue
            return RiskDecision(
                candidate=candidate, action="reject", final_qty=0,
                reason=str(e), rule_snapshot=_snap(eff),
            )


def _snap(rule: RiskRule) -> dict:
    return {
        "max_risk_per_trade_pct": rule.max_risk_per_trade_pct,
        "daily_loss_limit_pct": rule.daily_loss_limit_pct,
        "max_open_positions": rule.max_open_positions,
        "paper_only": rule.paper_only,
        "starting_equity": rule.starting_equity,
    }
