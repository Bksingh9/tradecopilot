from __future__ import annotations

from app.trading.models import RiskRule
from app.trading.risk import RiskContext, dynamic_risk_caps, effective_rule


def _rule(**o) -> RiskRule:
    return RiskRule(
        user_id=1, tenant_id=1,
        max_risk_per_trade_pct=o.get("max_risk_per_trade_pct", 1.0),
        daily_loss_limit_pct=o.get("daily_loss_limit_pct", 3.0),
        max_open_positions=o.get("max_open_positions", 5),
        starting_equity=o.get("starting_equity", 100_000.0),
    )


def _ctx(**o) -> RiskContext:
    return RiskContext(
        equity=o.get("equity", 100_000.0),
        realized_pnl_today=o.get("realized_pnl_today", 0.0),
        open_positions_count=o.get("open_positions_count", 0),
        recent_vol_pct=o.get("recent_vol_pct", 0.0),
        drawdown_pct=o.get("drawdown_pct", 0.0),
    )


def test_dynamic_caps_only_tighten_on_drawdown():
    base = _rule(max_risk_per_trade_pct=1.0, max_open_positions=5)
    out = dynamic_risk_caps(base, _ctx(drawdown_pct=6.0))
    assert out.max_risk_per_trade_pct <= base.max_risk_per_trade_pct
    assert out.max_open_positions <= base.max_open_positions


def test_dynamic_caps_compound_on_severe_drawdown():
    base = _rule(max_risk_per_trade_pct=1.0, max_open_positions=4)
    out = dynamic_risk_caps(base, _ctx(drawdown_pct=12.0))
    assert out.max_risk_per_trade_pct <= 0.25 * base.max_risk_per_trade_pct + 1e-9
    assert out.max_open_positions <= base.max_open_positions // 2


def test_dynamic_caps_only_tighten_on_high_vol():
    base = _rule(max_risk_per_trade_pct=1.0)
    out = dynamic_risk_caps(base, _ctx(recent_vol_pct=4.0))
    assert out.max_risk_per_trade_pct < base.max_risk_per_trade_pct


def test_dynamic_caps_never_loosen_when_calm():
    base = _rule(max_risk_per_trade_pct=1.0, max_open_positions=5)
    out = dynamic_risk_caps(base, _ctx(drawdown_pct=0.0, recent_vol_pct=0.5))
    assert out.max_risk_per_trade_pct == base.max_risk_per_trade_pct
    assert out.max_open_positions == base.max_open_positions


def test_effective_rule_applies_env_hard_caps(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "kill_switch_hard_daily_loss_pct", 2.0)
    monkeypatch.setattr(settings, "kill_switch_hard_max_open_positions", 3)
    base = _rule(daily_loss_limit_pct=10.0, max_open_positions=8)
    out = effective_rule(base)
    assert out.daily_loss_limit_pct == 2.0
    assert out.max_open_positions == 3
