"""Performance analytics + behavior profiling.

Pure functions over a list of Trade rows so they're easy to test. The admin
aggregate function works directly on a Session and produces *anonymized* output
(no emails, no per-user identifiers).

`get_user_behavior_profile(session, user)` returns a JSON-friendly dict
suitable for AI coach prompts — surfaces observable tendencies (overtrading,
revenge trading, oversizing after wins, time-of-day bias).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sqlmodel import Session, select

from app.auth.models import User
from app.trading.models import JournalEntry, Trade


@dataclass
class Summary:
    trade_count: int
    closed_count: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    avg_r: float
    best_trade: float
    worst_trade: float


def summary(trades: list[Trade]) -> Summary:
    closed = [t for t in trades if t.status == "CLOSED" and t.realized_pnl is not None]
    pnls = [t.realized_pnl for t in closed]
    rs = [t.r_multiple for t in closed if t.r_multiple is not None]
    if not closed:
        return Summary(len(trades), 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    wins = [p for p in pnls if p > 0]
    return Summary(
        trade_count=len(trades),
        closed_count=len(closed),
        win_rate=len(wins) / len(closed),
        total_pnl=float(sum(pnls)),
        avg_pnl=float(np.mean(pnls)),
        avg_r=float(np.mean(rs)) if rs else 0.0,
        best_trade=float(max(pnls)),
        worst_trade=float(min(pnls)),
    )


def by_symbol(trades: list[Trade]) -> dict[str, Summary]:
    g = defaultdict(list)
    for t in trades:
        g[t.symbol].append(t)
    return {sym: summary(rows) for sym, rows in g.items()}


def by_strategy(trades: list[Trade]) -> dict[str, Summary]:
    g = defaultdict(list)
    for t in trades:
        g[t.strategy or "manual"].append(t)
    return {k: summary(rows) for k, rows in g.items()}


def r_distribution(trades: list[Trade], buckets: tuple[float, ...] = (-3, -2, -1, 0, 1, 2, 3)) -> dict[str, int]:
    rs = [t.r_multiple for t in trades if t.r_multiple is not None]
    out: dict[str, int] = {}
    if not rs:
        return out
    edges = list(buckets)
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        out[f"{lo}..{hi}"] = sum(1 for r in rs if lo <= r < hi)
    out[f">={edges[-1]}"] = sum(1 for r in rs if r >= edges[-1])
    out[f"<{edges[0]}"] = sum(1 for r in rs if r < edges[0])
    return out


def by_hour_of_day(trades: list[Trade]) -> dict[int, Summary]:
    g: dict[int, list[Trade]] = defaultdict(list)
    for t in trades:
        if t.opened_at:
            g[t.opened_at.hour].append(t)
    return {h: summary(rows) for h, rows in sorted(g.items())}


def best_worst_hour(trades: list[Trade]) -> tuple[Optional[int], Optional[int]]:
    by_h = by_hour_of_day(trades)
    if not by_h:
        return None, None
    best = max(by_h.items(), key=lambda kv: kv[1].total_pnl)
    worst = min(by_h.items(), key=lambda kv: kv[1].total_pnl)
    return best[0], worst[0]


def filter_window(trades: list[Trade], start: Optional[datetime], end: Optional[datetime]) -> list[Trade]:
    out = trades
    if start:
        out = [t for t in out if t.opened_at and t.opened_at >= start]
    if end:
        out = [t for t in out if t.opened_at and t.opened_at <= end]
    return out


def streaks(trades: list[Trade]) -> dict[str, int]:
    closed = sorted(
        [t for t in trades if t.status == "CLOSED" and t.realized_pnl is not None and t.closed_at],
        key=lambda t: t.closed_at,
    )
    longest_win = longest_loss = 0
    cur_win = cur_loss = 0
    current = 0
    last_sign = 0
    for t in closed:
        if (t.realized_pnl or 0) > 0:
            cur_win += 1; cur_loss = 0
            longest_win = max(longest_win, cur_win)
            sign = 1
        elif (t.realized_pnl or 0) < 0:
            cur_loss += 1; cur_win = 0
            longest_loss = max(longest_loss, cur_loss)
            sign = -1
        else:
            sign = 0
        if sign != 0 and sign == last_sign:
            current = current + sign if sign > 0 else current - 1
        elif sign != 0:
            current = sign
        last_sign = sign
    return {"longest_win": longest_win, "longest_loss": longest_loss, "current": current}


def aggregate_overview_anonymized(session: Session) -> dict:
    rows = list(session.exec(select(Trade)).all())
    closed = [t for t in rows if t.status == "CLOSED" and t.realized_pnl is not None]
    pnls = [t.realized_pnl for t in closed]
    by_strat: dict[str, list[float]] = defaultdict(list)
    for t in closed:
        by_strat[t.strategy or "manual"].append(t.realized_pnl)

    return {
        "trade_count": len(rows),
        "closed_count": len(closed),
        "win_rate": (sum(1 for p in pnls if p > 0) / len(pnls)) if pnls else 0.0,
        "total_pnl": float(sum(pnls)) if pnls else 0.0,
        "avg_pnl": float(np.mean(pnls)) if pnls else 0.0,
        "median_pnl": float(np.median(pnls)) if pnls else 0.0,
        "by_strategy": {
            k: {"count": len(v), "total_pnl": float(sum(v)),
                "win_rate": (sum(1 for p in v if p > 0) / len(v)) if v else 0.0}
            for k, v in by_strat.items()
        },
        "tenants_with_activity": len({t.tenant_id for t in rows}),
        "users_with_activity": len({t.user_id for t in rows}),
    }


# ---------------------------------------------------------------------------
# Personalization: get_user_behavior_profile
# ---------------------------------------------------------------------------
def get_user_behavior_profile(
    session: Session, user: User, *, lookback_days: int = 60,
) -> dict:
    """JSON-friendly dict of observable tendencies for AI coach prompts.

    Tendencies are derived from rules:
      - overtrading_flag: ≥6 trades in the same symbol on the same calendar day
      - revenge_after_loss_flag: a new entry within 30 minutes of a losing close
      - oversizing_after_wins_flag: a trade with qty ≥ 1.5× recent median qty
        within 1 day of two consecutive wins
      - time_of_day_bias: hour with worst / best total P&L
    """
    end = datetime.utcnow()
    start = end - timedelta(days=lookback_days)
    trades = list(session.exec(
        select(Trade).where(Trade.user_id == user.id, Trade.opened_at >= start).order_by(Trade.opened_at)
    ).all())
    entries = list(session.exec(
        select(JournalEntry).where(JournalEntry.user_id == user.id, JournalEntry.created_at >= start)
    ).all())

    by_day_sym: dict[tuple, int] = defaultdict(int)
    for t in trades:
        if t.opened_at:
            by_day_sym[(t.opened_at.date(), t.symbol)] += 1
    overtrading_flag = any(c >= 6 for c in by_day_sym.values())

    closes = sorted(
        [t for t in trades if t.status == "CLOSED" and t.closed_at and (t.realized_pnl or 0) < 0],
        key=lambda t: t.closed_at,
    )
    opens = sorted([t for t in trades if t.opened_at], key=lambda t: t.opened_at)
    revenge_after_loss_flag = False
    for c in closes:
        for o in opens:
            if o.opened_at and c.closed_at and 0 < (o.opened_at - c.closed_at).total_seconds() <= 30 * 60:
                revenge_after_loss_flag = True
                break
        if revenge_after_loss_flag:
            break

    oversizing_flag = False
    if len(trades) >= 5:
        qtys = [t.qty for t in trades]
        med = float(np.median(qtys))
        wins = [t for t in trades if t.status == "CLOSED" and (t.realized_pnl or 0) > 0]
        wins_sorted = sorted(wins, key=lambda t: t.closed_at or datetime.min)
        for i in range(1, len(wins_sorted)):
            w1, w2 = wins_sorted[i - 1], wins_sorted[i]
            if not (w1.closed_at and w2.closed_at):
                continue
            if (w2.closed_at - w1.closed_at).total_seconds() > 86400:
                continue
            for o in opens:
                if (
                    o.opened_at and w2.closed_at
                    and 0 < (o.opened_at - w2.closed_at).total_seconds() <= 86400
                    and o.qty >= 1.5 * med
                ):
                    oversizing_flag = True
                    break
            if oversizing_flag:
                break

    hour_pnl: dict[int, float] = defaultdict(float)
    for t in trades:
        if t.opened_at and t.realized_pnl is not None:
            hour_pnl[t.opened_at.hour] += float(t.realized_pnl)
    if hour_pnl:
        worst_hour = min(hour_pnl.items(), key=lambda kv: kv[1])[0]
        best_hour = max(hour_pnl.items(), key=lambda kv: kv[1])[0]
    else:
        worst_hour = best_hour = None

    emo = Counter(e.emotion_tag for e in entries if e.emotion_tag).most_common(3)
    top_emotions = [{"tag": t, "count": c} for t, c in emo]

    return {
        "lookback_days": lookback_days,
        "sample_size": len(trades),
        "tendencies": {
            "overtrading_flag": bool(overtrading_flag),
            "revenge_after_loss_flag": bool(revenge_after_loss_flag),
            "oversizing_after_wins_flag": bool(oversizing_flag),
            "time_of_day_best_hour": best_hour,
            "time_of_day_worst_hour": worst_hour,
        },
        "top_emotions": top_emotions,
        "streaks": streaks(trades),
    }
