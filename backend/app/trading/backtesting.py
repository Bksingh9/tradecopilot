"""Minimal vectorized backtester driving any strategy from app.trading.strategies.

Returns standard metrics: CAGR, max drawdown, win rate, avg R, daily PnL series.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import numpy as np
import pandas as pd

from app.trading.strategies import Signal


@dataclass
class BacktestResult:
    cagr: float
    max_drawdown: float
    win_rate: float
    avg_r: float
    trade_count: int
    daily_pnl: pd.Series
    equity_curve: pd.Series
    trades: list[dict] = field(default_factory=list)


def _daily_returns_to_metrics(equity_curve: pd.Series) -> tuple[float, float]:
    if equity_curve.empty:
        return 0.0, 0.0
    days = max((equity_curve.index[-1] - equity_curve.index[0]).days, 1)
    cagr = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (365.25 / days) - 1
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return float(cagr), float(drawdown.min())


def backtest(
    df: pd.DataFrame,
    strategy: Callable[[pd.DataFrame, str], list[Signal]],
    symbol: str,
    starting_equity: float = 100_000.0,
    risk_per_trade_pct: float = 1.0,
    bar_lookback: int = 50,
    slippage_bps: float = 5.0,
) -> BacktestResult:
    """Bar-replay backtest. The strategy is called on each window slice; signals
    are simulated to fill at next bar's open with bps slippage. One position
    at a time per symbol.

    df: tz-aware OHLCV indexed by datetime.
    """
    if df is None or df.empty or len(df) < bar_lookback + 2:
        empty = pd.Series(dtype=float)
        return BacktestResult(0.0, 0.0, 0.0, 0.0, 0, empty, empty)

    equity = starting_equity
    open_pos: dict | None = None
    closed: list[dict] = []
    eq_points: list[tuple[datetime, float]] = []

    for i in range(bar_lookback, len(df) - 1):
        window = df.iloc[: i + 1]
        next_bar = df.iloc[i + 1]
        signals = strategy(window, symbol) or []
        bar = window.iloc[-1]

        # Manage existing position: stop / target.
        if open_pos is not None:
            hit_stop = (
                bar["low"] <= open_pos["stop"]
                if open_pos["side"] == "BUY"
                else bar["high"] >= open_pos["stop"]
            )
            hit_target = open_pos["target"] is not None and (
                bar["high"] >= open_pos["target"]
                if open_pos["side"] == "BUY"
                else bar["low"] <= open_pos["target"]
            )
            if hit_stop or hit_target:
                exit_px = float(open_pos["target"] if hit_target else open_pos["stop"])
                pnl_per_share = (exit_px - open_pos["entry"]) * (1 if open_pos["side"] == "BUY" else -1)
                pnl = pnl_per_share * open_pos["qty"]
                r = pnl_per_share / max(abs(open_pos["entry"] - open_pos["stop"]), 1e-9)
                equity += pnl
                closed.append(
                    {**open_pos, "exit": exit_px, "pnl": pnl, "r": r,
                     "exit_time": bar.name}
                )
                open_pos = None

        # Enter on a fresh signal if flat.
        if open_pos is None and signals:
            sig = signals[0]
            slip = next_bar["open"] * (slippage_bps / 10_000.0)
            entry = float(next_bar["open"] + (slip if sig.side == "BUY" else -slip))
            risk_per_share = abs(entry - sig.stop) or 1e-9
            qty = max(int((equity * risk_per_trade_pct / 100.0) // risk_per_share), 0)
            if qty > 0:
                open_pos = {
                    "side": sig.side,
                    "entry": entry,
                    "stop": sig.stop,
                    "target": sig.target,
                    "qty": qty,
                    "strategy": sig.strategy,
                    "entry_time": next_bar.name,
                }

        eq_points.append((bar.name, equity))

    eq = pd.Series(dict(eq_points), name="equity").sort_index()
    cagr, mdd = _daily_returns_to_metrics(eq)
    daily = eq.resample("1D").last().ffill().diff().fillna(0.0)
    win_rate = (
        sum(1 for t in closed if t["pnl"] > 0) / len(closed) if closed else 0.0
    )
    avg_r = float(np.mean([t["r"] for t in closed])) if closed else 0.0

    return BacktestResult(
        cagr=cagr,
        max_drawdown=mdd,
        win_rate=win_rate,
        avg_r=avg_r,
        trade_count=len(closed),
        daily_pnl=daily,
        equity_curve=eq,
        trades=closed,
    )
