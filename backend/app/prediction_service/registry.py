"""Joblib-backed model registry.

Layout on disk:
    {MODELS_DIR}/{strategy}/{symbol}_{tf}_{kind}/
        v_{YYYYMMDDhhmmss}.joblib
        v_{YYYYMMDDhhmmss}.meta.json
        latest -> v_{YYYYMMDDhhmmss}.joblib (symlink, or copied marker file in dev)

Each model is a sklearn-compatible estimator with optional `feature_names_in_`.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.common.logging import get_logger
from app.config import settings
from app.prediction_service.models import ModelConfig

logger = get_logger(__name__)


@dataclass
class LoadedModel:
    estimator: Any
    feature_names: list[str]
    meta: dict
    path: str


def _safe(s: str) -> str:
    return s.replace("/", "_").replace(" ", "_").upper()


def _models_dir() -> str:
    return getattr(settings, "models_dir", "./models")


def _bucket(cfg: ModelConfig) -> str:
    return os.path.join(
        _models_dir(),
        _safe(cfg.strategy),
        f"{_safe(cfg.symbol)}_{cfg.timeframe}_{cfg.kind}",
    )


def list_models(cfg: ModelConfig) -> list[str]:
    bucket = _bucket(cfg)
    if not os.path.isdir(bucket):
        return []
    return sorted(f for f in os.listdir(bucket) if f.endswith(".joblib"))


def save_model(
    cfg: ModelConfig,
    estimator: Any,
    feature_names: list[str],
    metrics: dict,
) -> str:
    import joblib

    bucket = _bucket(cfg)
    os.makedirs(bucket, exist_ok=True)
    version = "v_" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
    model_path = os.path.join(bucket, f"{version}.joblib")
    meta_path = os.path.join(bucket, f"{version}.meta.json")

    joblib.dump(estimator, model_path)
    with open(meta_path, "w") as f:
        json.dump({
            "version": version,
            "config": cfg.model_dump(),
            "feature_names": feature_names,
            "metrics": metrics,
            "saved_at": datetime.utcnow().isoformat(),
        }, f, default=str)

    # Update "latest" pointer.
    latest = os.path.join(bucket, "latest.json")
    with open(latest, "w") as f:
        json.dump({"version": version, "path": model_path, "meta": meta_path}, f)
    logger.info("model.saved %s version=%s", bucket, version)
    return model_path


def load_latest(cfg: ModelConfig) -> Optional[LoadedModel]:
    import joblib

    bucket = _bucket(cfg)
    latest_path = os.path.join(bucket, "latest.json")
    if not os.path.exists(latest_path):
        return None
    try:
        with open(latest_path) as f:
            ptr = json.load(f)
        with open(ptr["meta"]) as f:
            meta = json.load(f)
        estimator = joblib.load(ptr["path"])
        return LoadedModel(
            estimator=estimator,
            feature_names=meta.get("feature_names", []),
            meta=meta,
            path=ptr["path"],
        )
    except Exception as e:
        logger.warning("registry load failed for %s: %s", bucket, e)
        return None
