from __future__ import annotations

import pytest

from app.brokers.models import OrderRequest
from app.common.exceptions import RiskRuleViolation
from app.trading.models import RiskRule
from app.trading.risk import RiskContext, evaluate_order, position_size


def _rule(**overrides) -> RiskRule:
    return RiskRule(
        user_id=1,
        tenant_id=1,
        max_risk_per_trade_pct=overrides.get("max_risk_per_trade_pct", 1.0),
        daily_loss_limit_pct=overrides.get("daily_loss_limit_pct", 3.0),
        max_open_positions=overrides.get("max_open_positions", 5),
        restricted_symbols=overrides.get("restricted_symbols", []),
        paper_only=overrides.get("paper_only", True),
        starting_equity=overrides.get("starting_equity", 100_000.0),
    )


def _ctx(**o) -> RiskContext:
    return RiskContext(
        equity=o.get("equity", 100_000.0),
        realized_pnl_today=o.get("realized_pnl_today", 0.0),
        open_positions_count=o.get("open_positions_count", 0),
    )


def test_position_size_with_stop():
    qty = position_size(equity=100_000, risk_per_trade_pct=1.0, entry_price=200, stop_price=190)
    assert qty == 100


def test_position_size_no_stop_uses_notional_fallback():
    qty = position_size(equity=100_000, risk_per_trade_pct=2.0, entry_price=500, stop_price=None)
    assert qty == 4


def test_position_size_zero_when_invalid_inputs():
    assert position_size(equity=100, risk_per_trade_pct=1, entry_price=0, stop_price=10) == 0
    assert position_size(equity=100, risk_per_trade_pct=1, entry_price=10, stop_price=10) == 0


def test_restricted_symbol_blocked():
    order = OrderRequest(symbol="XYZ", side="BUY", qty=1, paper=True)
    rule = _rule(restricted_symbols=["XYZ"])
    with pytest.raises(RiskRuleViolation):
        evaluate_order(order, rule, _ctx())


def test_max_open_positions_blocked():
    order = OrderRequest(symbol="ABC", side="BUY", qty=1, paper=True)
    with pytest.raises(RiskRuleViolation):
        evaluate_order(order, _rule(max_open_positions=2), _ctx(open_positions_count=2))


def test_daily_loss_limit_blocked():
    order = OrderRequest(symbol="ABC", side="BUY", qty=1, paper=True)
    with pytest.raises(RiskRuleViolation):
        evaluate_order(order, _rule(daily_loss_limit_pct=2.0), _ctx(realized_pnl_today=-2500))


def test_paper_only_blocks_live():
    order = OrderRequest(symbol="ABC", side="BUY", qty=1, paper=False)
    with pytest.raises(RiskRuleViolation):
        evaluate_order(order, _rule(paper_only=True), _ctx())


def test_oversized_notional_blocked():
    order = OrderRequest(symbol="ABC", side="BUY", qty=300, order_type="LIMIT", price=1000, paper=True)
    with pytest.raises(RiskRuleViolation):
        evaluate_order(order, _rule(), _ctx())


def test_clean_order_passes():
    order = OrderRequest(symbol="ABC", side="BUY", qty=10, order_type="LIMIT", price=200, paper=True)
    evaluate_order(order, _rule(), _ctx())
