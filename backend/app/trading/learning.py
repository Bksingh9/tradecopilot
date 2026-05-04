"""Historical data ingestion + walk-forward backtesting + regime tagging."""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from itertools import product
from typing import Callable, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.common.logging import get_logger
from app.config import settings
from app.data import alpaca_data, global_equity, nse_india
from app.trading.backtesting import backtest as one_shot_backtest
from app.trading.models import BacktestRun
from app.trading.strategies import STRATEGIES

logger = get_logger(__name__)


# --- BacktestConfig ----------------------------------------------------------
class BacktestConfig(BaseModel):
    symbols: list[str]
    timeframe: str = "1d"
    start: datetime
    end: datetime
    fees_bps: float = 5.0
    slippage_bps: float = 5.0
    train_test_ratio: float = Field(0.7, ge=0.1, le=0.95)
    walk_forward_folds: int = Field(4, ge=1, le=20)
    starting_equity: float = 100_000.0
    risk_per_trade_pct: float = 1.0
    param_grid: dict[str, list] = Field(default_factory=dict)
    exchange_hint: Optional[str] = None


# --- Ingestion ---------------------------------------------------------------
def _cache_path(symbol: str, timeframe: str) -> str:
    safe = symbol.replace("/", "_").upper()
    return os.path.join(settings.data_cache_dir, f"{safe}_{timeframe}.parquet")


def _load_cached(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    path = _cache_path(symbol, timeframe)
    if not os.path.exists(path):
        return None
    try:
        return pd.read_parquet(path)
    except Exception as e:
        logger.warning("Failed to load cache %s: %s", path, e)
        return None


def _save_cached(symbol: str, timeframe: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    os.makedirs(settings.data_cache_dir, exist_ok=True)
    df.to_parquet(_cache_path(symbol, timeframe))


def ingest_history(
    symbols: list[str],
    timeframe: str = "1d",
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    exchange_hint: Optional[str] = None,
) -> dict[str, int]:
    """Fetch + persist OHLCV per symbol. Returns {symbol: row_count}."""
    end = end or datetime.now(timezone.utc)
    start = start or (end - timedelta(days=365 * 2))
    out: dict[str, int] = {}

    for sym in symbols:
        df: Optional[pd.DataFrame] = None
        s = sym.upper()
        is_indian = s.endswith(".NS") or s.endswith(".BO") or (exchange_hint or "").upper() in {"NSE", "BSE"}
        try:
            if is_indian:
                df = nse_india.get_ohlcv(s, start, end, timeframe)
            else:
                df = alpaca_data.get_ohlcv(s, start, end, timeframe) if (exchange_hint or "").upper() == "US" else None
                if df is None or df.empty:
                    df = global_equity.get_ohlcv(s, start, end, timeframe)
        except Exception as e:
            logger.warning("ingest failed for %s: %s", s, e)
            df = None

        if df is None or df.empty:
            out[sym] = 0
            continue

        _save_cached(sym, timeframe, df)
        out[sym] = len(df)

        # Append a fresh intraday point for NSE/BSE if available.
        if is_indian:
            try:
                q = nse_india.get_quote(s, exchange_hint=exchange_hint)
                bar = pd.DataFrame(
                    [[q.open or q.ltp, q.high or q.ltp, q.low or q.ltp, q.ltp, q.volume or 0]],
                    index=[pd.Timestamp(q.timestamp).tz_localize("UTC") if q.timestamp.tzinfo is None else pd.Timestamp(q.timestamp)],
                    columns=["open", "high", "low", "close", "volume"],
                )
                merged = pd.concat([df, bar]).sort_index()
                merged = merged[~merged.index.duplicated(keep="last")]
                _save_cached(sym, timeframe, merged)
            except Exception:
                pass

    return out


def load_history(symbol: str, timeframe: str = "1d") -> pd.DataFrame:
    df = _load_cached(symbol, timeframe)
    if df is not None and not df.empty:
        return df
    ingest_history([symbol], timeframe)
    return _load_cached(symbol, timeframe) or pd.DataFrame(
        columns=["open", "high", "low", "close", "volume"]
    )


# --- Regime tagging ---------------------------------------------------------
def tag_regime(df: pd.DataFrame, ema_span: int = 200, atr_period: int = 14) -> pd.Series:
    """Per-bar regime label.

    Labels: bull | bear | range | high_vol | low_vol | crash.
    Heuristic ladder, applied in order:
      1. crash  → 30-day return ≤ -15%
      2. high_vol → ATR% ≥ 95th percentile of trailing 252 bars
      3. low_vol  → ATR% ≤ 5th percentile of trailing 252 bars
      4. bull     → close > 200-EMA AND 60-day return ≥ 5%
      5. bear     → close < 200-EMA AND 60-day return ≤ -5%
      6. range    → otherwise
    """
    if df is None or df.empty:
        return pd.Series(dtype=object)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1,
    ).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    atr_pct = (atr / close) * 100.0
    ema = close.ewm(span=ema_span, adjust=False).mean()
    ret_60 = close.pct_change(60)
    ret_30 = close.pct_change(30)

    out = pd.Series("range", index=df.index, dtype=object)
    rolling_lo = atr_pct.rolling(252, min_periods=20).quantile(0.05)
    rolling_hi = atr_pct.rolling(252, min_periods=20).quantile(0.95)

    bull = (close > ema) & (ret_60 >= 0.05)
    bear = (close < ema) & (ret_60 <= -0.05)
    high_vol = atr_pct >= rolling_hi
    low_vol = atr_pct <= rolling_lo
    crash = ret_30 <= -0.15

    out.loc[bull] = "bull"
    out.loc[bear] = "bear"
    out.loc[low_vol.fillna(False)] = "low_vol"
    out.loc[high_vol.fillna(False)] = "high_vol"
    out.loc[crash.fillna(False)] = "crash"
    return out


# --- Metrics ----------------------------------------------------------------
def _sharpe(equity: pd.Series, freq_per_year: int = 252) -> float:
    if equity is None or equity.empty:
        return 0.0
    r = equity.pct_change().dropna()
    if r.std(ddof=0) == 0 or r.empty:
        return 0.0
    return float(math.sqrt(freq_per_year) * r.mean() / r.std(ddof=0))


def _profit_factor(trades: list[dict]) -> float:
    gross_win = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = -sum(t["pnl"] for t in trades if t["pnl"] < 0)
    if gross_loss == 0:
        return float("inf") if gross_win > 0 else 0.0
    return float(gross_win / gross_loss)


def _trade_metrics(trades: list[dict]) -> dict:
    closed = [t for t in trades if "pnl" in t]
    if not closed:
        return {
            "trade_count": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "total_pnl": 0.0, "avg_r": 0.0,
        }
    pnls = [t["pnl"] for t in closed]
    rs = [t.get("r", 0.0) for t in closed]
    return {
        "trade_count": len(closed),
        "win_rate": float(sum(1 for p in pnls if p > 0) / len(pnls)),
        "profit_factor": _profit_factor(closed),
        "total_pnl": float(sum(pnls)),
        "avg_r": float(np.mean(rs)) if rs else 0.0,
    }


# --- Walk-forward -----------------------------------------------------------
def _slice_window(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    if df.empty:
        return df
    if df.index.tz is None:
        df = df.tz_localize("UTC")
    return df.loc[(df.index >= pd.Timestamp(start, tz="UTC")) & (df.index <= pd.Timestamp(end, tz="UTC"))]


def _select_best_params(
    train_df: pd.DataFrame,
    strategy_fn: Callable,
    grid: dict[str, list],
    symbol: str,
    starting_equity: float,
    risk_pct: float,
    slippage_bps: float,
) -> tuple[dict, float]:
    if not grid:
        return {}, 0.0
    keys = list(grid.keys())
    best_params: dict = {}
    best_eq = -math.inf
    for combo in product(*(grid[k] for k in keys)):
        params = dict(zip(keys, combo))

        def _wrapped(df, sym=symbol, fn=strategy_fn, p=params):
            return fn(df, sym, **p)

        res = one_shot_backtest(
            train_df, _wrapped, symbol,
            starting_equity=starting_equity,
            risk_per_trade_pct=risk_pct,
            slippage_bps=slippage_bps,
        )
        final = float(res.equity_curve.iloc[-1]) if not res.equity_curve.empty else starting_equity
        if final > best_eq:
            best_eq = final
            best_params = params
    return best_params, best_eq


def run_walk_forward(strategy_name: str, config: BacktestConfig) -> dict:
    if strategy_name not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    strategy_fn = STRATEGIES[strategy_name]

    all_trades: list[dict] = []
    fold_results: list[dict] = []
    combined_equity = pd.Series(dtype=float)
    by_regime_trades: dict[str, list[dict]] = {}

    for sym in config.symbols:
        df = load_history(sym, config.timeframe)
        df = _slice_window(df, config.start, config.end)
        if df.empty or len(df) < 200:
            fold_results.append({"symbol": sym, "skipped": "insufficient_data", "rows": len(df)})
            continue

        regime = tag_regime(df)

        n = len(df)
        fold_size = n // (config.walk_forward_folds + 1)
        if fold_size < 50:
            fold_results.append({"symbol": sym, "skipped": "fold_too_small"})
            continue

        for fold_i in range(config.walk_forward_folds):
            train_end = (fold_i + 1) * fold_size
            test_end = min((fold_i + 2) * fold_size, n)
            train_df = df.iloc[:train_end]
            test_df = df.iloc[train_end:test_end]
            if test_df.empty:
                continue

            best_params, _ = _select_best_params(
                train_df, strategy_fn, config.param_grid, sym,
                config.starting_equity, config.risk_per_trade_pct, config.slippage_bps,
            )

            def _wrapped(d, sym=sym, fn=strategy_fn, p=best_params):
                return fn(d, sym, **p)

            res = one_shot_backtest(
                test_df, _wrapped, sym,
                starting_equity=config.starting_equity,
                risk_per_trade_pct=config.risk_per_trade_pct,
                slippage_bps=config.slippage_bps,
            )
            fold_results.append({
                "symbol": sym, "fold": fold_i, "params": best_params,
                "cagr": res.cagr, "max_dd": res.max_drawdown,
                "win_rate": res.win_rate, "trade_count": res.trade_count,
            })
            for t in res.trades:
                tagged = dict(t)
                # Tag the trade with the regime at entry_time (closest indexed bar).
                ts = t.get("entry_time")
                tag = None
                try:
                    if ts is not None:
                        idx = regime.index.searchsorted(pd.Timestamp(ts))
                        if 0 <= idx < len(regime):
                            tag = regime.iloc[idx]
                except Exception:
                    pass
                tagged["regime"] = tag or "unknown"
                all_trades.append(tagged)
                by_regime_trades.setdefault(tagged["regime"], []).append(tagged)

            if not res.equity_curve.empty:
                combined_equity = pd.concat([combined_equity, res.equity_curve])

    metrics_overall = _trade_metrics(all_trades)
    if not combined_equity.empty:
        days = max((combined_equity.index[-1] - combined_equity.index[0]).days, 1)
        cagr = (combined_equity.iloc[-1] / combined_equity.iloc[0]) ** (365.25 / days) - 1
        rolling_max = combined_equity.cummax()
        max_dd = float(((combined_equity - rolling_max) / rolling_max).min())
    else:
        cagr, max_dd = 0.0, 0.0

    return {
        "strategy": strategy_name,
        "config": config.model_dump(mode="json"),
        "metrics": {
            "cagr": float(cagr),
            "sharpe": _sharpe(combined_equity),
            "max_dd": max_dd,
            **metrics_overall,
            "by_regime": {k: _trade_metrics(v) for k, v in by_regime_trades.items()},
        },
        "folds": fold_results,
    }


# --- Persistence helpers -----------------------------------------------------
def save_run(session: Session, run: BacktestRun) -> BacktestRun:
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def execute_run(run_id: int) -> None:
    """APScheduler entrypoint. Loads BacktestRun, runs, saves metrics."""
    from app.database import session_scope

    with session_scope() as session:
        row = session.get(BacktestRun, run_id)
        if not row:
            return
        try:
            row.status = "running"
            session.add(row)
            session.commit()

            cfg = BacktestConfig(**row.config_json)
            result = run_walk_forward(row.strategy, cfg)
            row.metrics_json = result
            row.status = "done"
            row.finished_at = datetime.utcnow()
        except Exception as e:
            logger.exception("backtest run %s failed", run_id)
            row.status = "failed"
            row.error = str(e)[:500]
            row.finished_at = datetime.utcnow()
        finally:
            session.add(row)
            session.commit()
