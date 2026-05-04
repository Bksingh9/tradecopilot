"""End-to-end decision cycle in advisory mode → outcomes are 'proposed' only."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd

from app.agent_orchestrator import run_decision_cycle
from app.auth import service as auth_service
from app.vector_memory import db as vm_db


def _ohlcv(n: int = 250) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    closes = 100 + np.cumsum(rng.normal(0.05, 1, n))   # slight upward drift to provoke a momentum BUY
    idx = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc), periods=n, freq="D")
    return pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": 1000,
    }, index=idx)


def test_advisory_only_proposes(session, monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.models_dir", str(tmp_path))
    vm_db._reset_backend_for_tests()

    user = auth_service.signup(session, "ml1@example.com", "password123")
    df = _ohlcv()

    with patch("app.agent_orchestrator.orchestrator.get_ohlcv", return_value=df):
        outcomes = run_decision_cycle(session, user, ["TEST"], timeframe="1d")

    assert isinstance(outcomes, list)
    # In advisory mode, no candidate is ever 'placed' or 'blocked'.
    for o in outcomes:
        if o.execution is None:
            continue
        assert o.execution.status in {"proposed", "skipped"}
