"""Alias package — re-exports backtester + walk-forward + regime tagging."""
from app.trading.backtesting import backtest, BacktestResult  # noqa: F401
from app.trading.learning import (  # noqa: F401
    BacktestConfig, ingest_history, load_history, run_walk_forward, tag_regime, execute_run,
)
