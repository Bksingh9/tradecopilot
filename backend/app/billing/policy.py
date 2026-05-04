"""Plan-gating policy.

Plans:
  free  → advisory only, 1 active symbol, no full_auto.
  pro   → semi_auto allowed, up to 25 active symbols.
  team  → full_auto eligible (after paper-qualification + consent), up to 100 symbols.

Centralizes the rules so endpoints can call `enforce_plan(user, action, payload)`
and get a single source of truth.
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.auth.models import User
from app.billing.models import Subscription
from app.common.exceptions import PermissionDenied


PLANS = {
    "free": {
        "max_symbols": 1,
        "modes_allowed": {"advisory"},
        "backtest_runs_per_day": 5,
    },
    "pro": {
        "max_symbols": 25,
        "modes_allowed": {"advisory", "semi_auto"},
        "backtest_runs_per_day": 50,
    },
    "team": {
        "max_symbols": 100,
        "modes_allowed": {"advisory", "semi_auto", "full_auto"},
        "backtest_runs_per_day": 500,
    },
}


def get_plan(session: Session, user: User) -> str:
    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user.id)
    ).first()
    return (sub.plan if sub else "free").lower()


def enforce_plan(session: Session, user: User, action: str, payload: dict[str, Any] | None = None) -> None:
    """Raise PermissionDenied if `action` is not allowed under the user's plan.

    Supported actions:
      "agent.cycle"  payload: {"symbols": [...]}        — checks max_symbols
      "autonomy.set" payload: {"mode": "semi_auto"}     — checks modes_allowed
      "backtest.run" payload: {"runs_today": int}       — checks daily quota
    """
    plan = get_plan(session, user)
    rules = PLANS.get(plan, PLANS["free"])
    payload = payload or {}

    if action == "agent.cycle":
        n = len(payload.get("symbols") or [])
        if n > rules["max_symbols"]:
            raise PermissionDenied(
                f"Plan '{plan}' allows {rules['max_symbols']} symbols per cycle (got {n})"
            )
    elif action == "autonomy.set":
        mode = payload.get("mode")
        if mode not in rules["modes_allowed"]:
            raise PermissionDenied(
                f"Plan '{plan}' does not allow autonomy mode '{mode}'"
            )
    elif action == "backtest.run":
        used = int(payload.get("runs_today") or 0)
        if used >= rules["backtest_runs_per_day"]:
            raise PermissionDenied(
                f"Plan '{plan}' allows {rules['backtest_runs_per_day']} backtest runs/day"
            )
