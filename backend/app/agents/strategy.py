"""Strategy agent — translates AnalystSignal into concrete CandidateTrade(s).

Picks among existing strategies (momentum, mean_reversion, ORB) by regime hint.
Position sizing is intentionally minimal here; the Risk agent does the final
sizing using the user's RiskRule + dynamic caps.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.agents.models import AnalystSignal, CandidateTrade
from app.auth.models import User
from app.data import get_ohlcv
from app.trading.strategies import STRATEGIES


class StrategyAgent:
    def propose(
        self,
        signal: AnalystSignal,
        user: User,
    ) -> list[CandidateTrade]:
        # Pick strategies by regime; default to momentum.
        wants: list[str] = []
        regime = (signal.regime or "").lower()
        if regime in {"bull", "bear", "high_vol"}:
            wants = ["momentum"]
        elif regime in {"range", "low_vol"}:
            wants = ["mean_reversion"]
        elif regime == "crash":
            wants = []  # do nothing in crash regime — let the user decide manually
        else:
            wants = ["momentum"]

        if not wants:
            return []

        # We need a fresh dataframe to feed the strategy fns directly.
        end = datetime.utcnow()
        start = end - timedelta(days=200)
        df = get_ohlcv(signal.symbol, start, end, signal.timeframe, exchange_hint=signal.exchange)

        cands: list[CandidateTrade] = []
        for strategy_name in wants:
            fn = STRATEGIES.get(strategy_name)
            if fn is None:
                continue
            for sig in fn(df, signal.symbol) or []:
                # The Strategy agent uses a *placeholder* qty=1 and lets Risk size it.
                cands.append(
                    CandidateTrade(
                        symbol=signal.symbol,
                        exchange=signal.exchange,
                        side=sig.side,
                        qty=1,
                        entry=sig.entry,
                        stop=sig.stop,
                        target=sig.target,
                        strategy=sig.strategy,
                        rationale=f"{sig.rationale} | analyst.p_up={signal.p_up:.2f} regime={signal.regime}",
                        paper=True,
                    )
                )
        return cands
