"""Training + walk-forward evaluation. Runs as background jobs only.

Default learner: sklearn `GradientBoostingClassifier`. XGBoost / LightGBM are
loaded lazily when `cfg.kind` requests them. LSTM / Transformer kinds fall back
to GBM with a logged warning until you wire a real implementation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.common.logging import get_logger
from app.data import get_ohlcv
from app.prediction_service import registry
from app.prediction_service.features import make_xy
from app.prediction_service.models import ModelConfig

logger = get_logger(__name__)


# -- Learner selection -----------------------------------------------------
def _select_estimator(cfg: ModelConfig) -> Any:
    kind = cfg.kind

    if kind == "xgboost":
        try:
            import xgboost as xgb  # type: ignore
            return xgb.XGBClassifier(
                n_estimators=cfg.hyperparams.get("n_estimators", 200),
                max_depth=cfg.hyperparams.get("max_depth", 4),
                learning_rate=cfg.hyperparams.get("learning_rate", 0.05),
                subsample=cfg.hyperparams.get("subsample", 0.8),
                use_label_encoder=False,
                eval_metric="logloss",
                tree_method="hist",
            )
        except Exception as e:
            logger.warning("xgboost unavailable (%s) — falling back to sklearn GBM", e)

    if kind == "lightgbm":
        try:
            import lightgbm as lgb  # type: ignore
            return lgb.LGBMClassifier(
                n_estimators=cfg.hyperparams.get("n_estimators", 300),
                max_depth=cfg.hyperparams.get("max_depth", -1),
                learning_rate=cfg.hyperparams.get("learning_rate", 0.05),
                subsample=cfg.hyperparams.get("subsample", 0.8),
            )
        except Exception as e:
            logger.warning("lightgbm unavailable (%s) — falling back to sklearn GBM", e)

    if kind in {"lstm_stub", "transformer_stub"}:
        logger.warning(
            "%s requested but no implementation wired — training a sklearn GBM as a stand-in",
            kind,
        )

    # Default: pure-sklearn GradientBoostingClassifier.
    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(
        n_estimators=cfg.hyperparams.get("n_estimators", 200),
        max_depth=cfg.hyperparams.get("max_depth", 3),
        learning_rate=cfg.hyperparams.get("learning_rate", 0.05),
        subsample=cfg.hyperparams.get("subsample", 0.9),
    )


# -- Walk-forward + metrics ------------------------------------------------
def _walk_forward_split(X: pd.DataFrame, y: pd.Series, val_fraction: float):
    n = len(X)
    if n < 100:
        return None
    n_val = max(int(n * val_fraction), 20)
    return X.iloc[: n - n_val], y.iloc[: n - n_val], X.iloc[n - n_val :], y.iloc[n - n_val :]


def _metrics(y_true: pd.Series, y_prob: np.ndarray) -> dict:
    from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

    y_pred = (y_prob >= 0.5).astype(int)
    out: dict = {
        "n": int(len(y_true)),
        "pos_rate": float(np.mean(y_true)) if len(y_true) else 0.0,
        "accuracy": float(accuracy_score(y_true, y_pred)) if len(y_true) else 0.0,
        "log_loss": float(log_loss(y_true, np.clip(y_prob, 1e-6, 1 - 1e-6), labels=[0, 1])) if len(y_true) else 0.0,
    }
    try:
        if len(np.unique(y_true)) == 2:
            out["roc_auc"] = float(roc_auc_score(y_true, y_prob))
    except Exception:
        pass
    return out


# -- Public API ------------------------------------------------------------
def _load_history(cfg: ModelConfig) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=cfg.train_window_days)
    return get_ohlcv(cfg.symbol, start, end, cfg.timeframe, exchange_hint=cfg.exchange_hint)


def train_model(cfg: ModelConfig) -> dict:
    df = _load_history(cfg)
    if df is None or df.empty:
        logger.warning("train_model: no data for %s/%s", cfg.symbol, cfg.timeframe)
        return {"ok": False, "reason": "no_data"}

    if cfg.label_kind != "sign":
        # Regression isn't wired yet for the default classifier.
        logger.warning("train_model: only label_kind=sign is supported in v1; coercing")
        cfg = cfg.model_copy(update={"label_kind": "sign"})

    X, y = make_xy(df, cfg)
    split = _walk_forward_split(X, y, cfg.val_fraction)
    if split is None:
        return {"ok": False, "reason": "insufficient_rows", "rows": int(len(X))}
    X_tr, y_tr, X_va, y_va = split

    est = _select_estimator(cfg)
    est.fit(X_tr.values, y_tr.values)

    if hasattr(est, "predict_proba"):
        prob_va = est.predict_proba(X_va.values)[:, 1]
    else:
        prob_va = est.predict(X_va.values).astype(float)
    metrics_val = _metrics(y_va, prob_va)

    path = registry.save_model(cfg, est, list(X.columns), metrics_val)
    logger.info("train_model done symbol=%s metrics=%s", cfg.symbol, metrics_val)
    return {"ok": True, "metrics": metrics_val, "model_path": path, "rows": int(len(X))}


def evaluate_model(cfg: ModelConfig) -> dict:
    df = _load_history(cfg)
    if df is None or df.empty:
        return {"ok": False, "reason": "no_data"}
    X, y = make_xy(df, cfg)
    loaded = registry.load_latest(cfg)
    if loaded is None:
        return {"ok": False, "reason": "no_model"}
    est = loaded.estimator
    if hasattr(est, "predict_proba"):
        prob = est.predict_proba(X.values)[:, 1]
    else:
        prob = est.predict(X.values).astype(float)
    return {"ok": True, "metrics": _metrics(y, prob), "version": loaded.meta.get("version")}


# Background-job entrypoint (APScheduler).
def execute_training_job(cfg_dict: dict) -> None:
    cfg = ModelConfig(**cfg_dict)
    try:
        out = train_model(cfg)
        logger.info("training job result: %s", out)
    except Exception as e:
        logger.exception("training job failed: %s", e)
