from __future__ import annotations

from datetime import datetime

from app.journal import analytics
from app.trading.models import Trade


def _t(**kw) -> Trade:
    return Trade(
        user_id=1, tenant_id=1,
        broker="alpaca",
        symbol=kw.get("symbol", "AAPL"),
        side=kw.get("side", "BUY"),
        qty=kw.get("qty", 10),
        entry_price=kw.get("entry_price", 100.0),
        exit_price=kw.get("exit_price"),
        stop_price=kw.get("stop_price", 90.0),
        target_price=kw.get("target_price", 120.0),
        realized_pnl=kw.get("realized_pnl"),
        r_multiple=kw.get("r_multiple"),
        strategy=kw.get("strategy", "momentum"),
        status=kw.get("status", "CLOSED"),
        opened_at=kw.get("opened_at", datetime(2024, 1, 1, 10, 0)),
        closed_at=kw.get("closed_at", datetime(2024, 1, 1, 14, 0)),
    )


def test_summary_basic():
    import pytest as _pt
    trades = [
        _t(realized_pnl=100, r_multiple=1.0),
        _t(realized_pnl=-50, r_multiple=-0.5),
        _t(realized_pnl=200, r_multiple=2.0),
    ]
    s = analytics.summary(trades)
    assert s.closed_count == 3
    assert s.win_rate == _pt.approx(2 / 3)
    assert s.total_pnl == 250
    assert s.best_trade == 200
    assert s.worst_trade == -50


def test_by_symbol_groups_correctly():
    trades = [
        _t(symbol="AAPL", realized_pnl=10),
        _t(symbol="AAPL", realized_pnl=20),
        _t(symbol="MSFT", realized_pnl=5),
    ]
    bs = analytics.by_symbol(trades)
    assert bs["AAPL"].total_pnl == 30
    assert bs["MSFT"].total_pnl == 5


def test_r_distribution_buckets():
    trades = [_t(r_multiple=r) for r in [-2.5, -0.5, 0.5, 1.5, 3.5]]
    d = analytics.r_distribution(trades)
    assert d["<-3"] == 0
    assert d[">=3"] == 1


def test_best_worst_hour():
    trades = [
        _t(opened_at=datetime(2024, 1, 1, 9), realized_pnl=-100),
        _t(opened_at=datetime(2024, 1, 1, 14), realized_pnl=300),
    ]
    best, worst = analytics.best_worst_hour(trades)
    assert best == 14 and worst == 9


def test_streaks():
    base = datetime(2024, 1, 1)
    trades = [
        _t(realized_pnl=10, closed_at=datetime(2024, 1, 1)),
        _t(realized_pnl=20, closed_at=datetime(2024, 1, 2)),
        _t(realized_pnl=-5, closed_at=datetime(2024, 1, 3)),
        _t(realized_pnl=-7, closed_at=datetime(2024, 1, 4)),
        _t(realized_pnl=-9, closed_at=datetime(2024, 1, 5)),
    ]
    s = analytics.streaks(trades)
    assert s["longest_win"] == 2
    assert s["longest_loss"] == 3
    # current run is a loss streak
    assert s["current"] < 0
