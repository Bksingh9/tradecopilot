"""Risk engine — hard caps, dynamic caps, kill switch, audit hooks.

Hard caps come from environment (`KILL_SWITCH_HARD_*`). They cannot be loosened
by AI or by user edits. Dynamic caps tighten further on volatility/drawdown.
The kill switch short-circuits every order. All set/clear writes an AuditEvent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlmodel import Session, select

from app.audit import service as audit
from app.brokers.models import OrderRequest
from app.common.exceptions import RiskRuleViolation
from app.common.logging import get_logger
from app.config import settings
from app.trading.models import KillSwitch, RiskRule, Trade

logger = get_logger(__name__)


@dataclass
class RiskContext:
    equity: float
    realized_pnl_today: float
    open_positions_count: int
    recent_vol_pct: float = 0.0
    drawdown_pct: float = 0.0


# ---------------------------------------------------------------------------
def _copy_rule(rule: RiskRule, **overrides) -> RiskRule:
    """SQLModel-safe shallow copy with field overrides.

    `dataclasses.replace()` only works on dataclass instances; RiskRule is a
    SQLModel/Pydantic table class, so we use model_copy/model_dump to build a
    detached (non-DB-bound) RiskRule with the same values plus overrides.
    """
    data = rule.model_dump()
    data.update(overrides)
    # Drop primary key so the copy is not treated as the persisted row.
    data.pop("id", None)
    return RiskRule(**data)


def effective_rule(rule: RiskRule) -> RiskRule:
    """Apply env-driven hard caps. Most conservative wins."""
    return _copy_rule(
        rule,
        daily_loss_limit_pct=min(rule.daily_loss_limit_pct, settings.kill_switch_hard_daily_loss_pct),
        max_open_positions=min(rule.max_open_positions, settings.kill_switch_hard_max_open_positions),
    )


def dynamic_risk_caps(rule: RiskRule, ctx: RiskContext) -> RiskRule:
    """Tighten further on drawdown / volatility. Never loosens."""
    out = effective_rule(rule)
    new_risk = out.max_risk_per_trade_pct
    new_max_pos = out.max_open_positions

    if ctx.drawdown_pct >= 5.0:
        new_risk *= 0.5
        new_max_pos = max(1, new_max_pos - 1)
    if ctx.drawdown_pct >= 10.0:
        new_risk *= 0.5
        new_max_pos = max(1, new_max_pos // 2)
    if ctx.recent_vol_pct >= 3.0:
        new_risk *= 0.75

    return _copy_rule(
        out,
        max_risk_per_trade_pct=min(out.max_risk_per_trade_pct, new_risk),
        max_open_positions=min(out.max_open_positions, new_max_pos),
    )


# ---------------------------------------------------------------------------
def position_size(
    equity: float, risk_per_trade_pct: float,
    entry_price: float, stop_price: Optional[float],
) -> int:
    if entry_price <= 0:
        return 0
    if not stop_price or stop_price <= 0:
        notional = equity * (risk_per_trade_pct / 100.0)
        return max(int(notional // entry_price), 0)
    risk_per_share = abs(entry_price - stop_price)
    if risk_per_share <= 0:
        return 0
    rupee_risk = equity * (risk_per_trade_pct / 100.0)
    return max(int(rupee_risk // risk_per_share), 0)


# ---------------------------------------------------------------------------
def evaluate_order(order: OrderRequest, rule: RiskRule, ctx: RiskContext) -> None:
    eff = dynamic_risk_caps(rule, ctx)

    if order.symbol.upper() in {s.upper() for s in (eff.restricted_symbols or [])}:
        raise RiskRuleViolation(f"{order.symbol} is in your restricted symbols list")

    if eff.paper_only and not order.paper:
        raise RiskRuleViolation("paper_only=True — live orders blocked")

    if ctx.open_positions_count >= eff.max_open_positions:
        raise RiskRuleViolation(
            f"Max open positions reached ({ctx.open_positions_count}/{eff.max_open_positions})"
        )

    daily_loss_limit_value = ctx.equity * (eff.daily_loss_limit_pct / 100.0)
    if ctx.realized_pnl_today <= -daily_loss_limit_value:
        raise RiskRuleViolation(
            f"Daily loss limit hit ({ctx.realized_pnl_today:.2f} ≤ -{daily_loss_limit_value:.2f})"
        )

    if order.order_type == "LIMIT" and not order.price:
        raise RiskRuleViolation("LIMIT order missing price")

    if order.price:
        notional = order.qty * order.price
        if notional > ctx.equity * 0.20:
            raise RiskRuleViolation(
                f"Order notional ({notional:.0f}) > 20% of equity ({ctx.equity:.0f})"
            )


# ---------------------------------------------------------------------------
def realized_pnl_today(session: Session, user_id: int, today: Optional[date] = None) -> float:
    today = today or datetime.utcnow().date()
    rows = session.exec(
        select(Trade).where(Trade.user_id == user_id, Trade.status == "CLOSED")
    ).all()
    total = 0.0
    for t in rows:
        if t.closed_at and t.closed_at.date() == today and t.realized_pnl is not None:
            total += t.realized_pnl
    return total


def open_positions_count(session: Session, user_id: int) -> int:
    return len(
        session.exec(select(Trade).where(Trade.user_id == user_id, Trade.status == "OPEN")).all()
    )


def build_context(
    session: Session, user_id: int, rule: RiskRule,
    *, recent_vol_pct: float = 0.0, drawdown_pct: float = 0.0,
) -> RiskContext:
    return RiskContext(
        equity=rule.starting_equity,
        realized_pnl_today=realized_pnl_today(session, user_id),
        open_positions_count=open_positions_count(session, user_id),
        recent_vol_pct=recent_vol_pct,
        drawdown_pct=drawdown_pct,
    )


# ---------------------------------------------------------------------------
def is_blocked(session: Session, user_id: int, tenant_id: int) -> Optional[str]:
    row = session.exec(
        select(KillSwitch).where(
            KillSwitch.tenant_id == tenant_id,
            KillSwitch.active == True,  # noqa: E712
            ((KillSwitch.scope == "tenant") | (KillSwitch.user_id == user_id)),
        )
    ).first()
    return row.reason if row else None


def set_kill_switch(
    session: Session,
    *, tenant_id: int, user_id: Optional[int],
    scope: str, reason: str, set_by: str,
) -> KillSwitch:
    row = KillSwitch(
        tenant_id=tenant_id, user_id=user_id, scope=scope,
        reason=reason, set_by=set_by, active=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    audit.record(
        session, tenant_id=tenant_id, user_id=user_id, actor=set_by,
        action="kill_switch.set",
        subject_type="kill_switch", subject_id=row.id,
        payload={"scope": scope, "reason": reason[:200]},
    )
    logger.warning("kill_switch.set scope=%s tenant=%s user=%s by=%s",
                   scope, tenant_id, user_id, set_by)
    return row


def clear_kill_switch(session: Session, kill_id: int, *, by: str) -> bool:
    row = session.get(KillSwitch, kill_id)
    if not row or not row.active:
        return False
    row.active = False
    row.cleared_at = datetime.utcnow()
    session.add(row)
    session.commit()
    audit.record(
        session, tenant_id=row.tenant_id, user_id=row.user_id, actor=by,
        action="kill_switch.cleared",
        subject_type="kill_switch", subject_id=kill_id,
        payload={"scope": row.scope},
    )
    logger.warning("kill_switch.cleared id=%s by=%s", kill_id, by)
    return True
