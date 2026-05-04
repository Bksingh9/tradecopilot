"""Registry round-trip + baseline-on-miss behavior."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.prediction_service import inference, registry
from app.prediction_service.features import build_feature_matrix
from app.prediction_service.models import ModelConfig


def _synthetic(n: int = 250) -> pd.DataFrame:
    rng = np.random.default_rng(2)
    closes = 100 + np.cumsum(rng.normal(0, 1, n))
    idx = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc), periods=n, freq="D")
    return pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": 1000,
    }, index=idx)


def test_registry_miss_returns_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.models_dir", str(tmp_path))
    res = inference.get_prediction("MISSINGSYM", "1d", _synthetic())
    assert res.model_version == "baseline"
    assert 0.0 <= res.prob_up <= 1.0
    assert any("baseline" in n.lower() or "no trained" in n.lower() for n in res.notes)


def test_round_trip_save_and_load(monkeypatch, tmp_path):
    from sklearn.linear_model import LogisticRegression

    monkeypatch.setattr("app.config.settings.models_dir", str(tmp_path))

    cfg = ModelConfig(symbol="ABC", timeframe="1d")
    df = _synthetic()
    X = build_feature_matrix(df).dropna()
    y = (X["ret_5"] > 0).astype(int)

    est = LogisticRegression(max_iter=200).fit(X.values, y.values)
    registry.save_model(cfg, est, list(X.columns), {"n": int(len(X))})
    loaded = registry.load_latest(cfg)
    assert loaded is not None
    assert hasattr(loaded.estimator, "predict_proba")
    assert loaded.feature_names == list(X.columns)

    res = inference.get_prediction("ABC", "1d", df)
    assert res.model_version != "baseline"
    assert 0.0 <= res.prob_up <= 1.0
