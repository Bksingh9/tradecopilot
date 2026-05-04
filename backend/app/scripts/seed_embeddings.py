"""Seed historical market window embeddings into vector_memory.

Walks the parquet cache under `DATA_CACHE_DIR`, slides a window over each
file, embeds each window via `market_window_embedding`, tags it with the
regime label from `tag_regime`, and upserts into vector_memory under
`tenant_id`.

Usage:
    python -m app.scripts.seed_embeddings --tenant 1
    python -m app.scripts.seed_embeddings --tenant 1 --window 90 --stride 30
    python -m app.scripts.seed_embeddings --tenant 1 --symbols RELIANCE.NS_1d AAPL_1d
    python -m app.scripts.seed_embeddings --tenant 1 --dry-run

The script is *idempotent* — re-running with the same window/stride upserts
the same `subject_id`s in place. It's safe to run inside Docker
(`docker-compose exec api python -m app.scripts.seed_embeddings --tenant 1`).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Iterable

import pandas as pd

from app.common.logging import configure_logging, get_logger
from app.config import settings
from app.trading.learning import tag_regime
from app.vector_memory import market_window_embedding, upsert_market_window

configure_logging()
logger = get_logger("seed_embeddings")


def _iter_parquet_files(symbols: list[str] | None) -> Iterable[tuple[str, str]]:
    """Yields (file_basename, path)."""
    root = settings.data_cache_dir
    if not os.path.isdir(root):
        logger.error("DATA_CACHE_DIR not found: %s", root)
        return
    for name in sorted(os.listdir(root)):
        if not name.endswith(".parquet"):
            continue
        base = name[:-len(".parquet")]
        if symbols and base not in symbols:
            continue
        yield base, os.path.join(root, name)


def _windows(df: pd.DataFrame, *, window: int, stride: int):
    n = len(df)
    if n < window + 1:
        return
    for end in range(window, n, stride):
        sl = df.iloc[end - window : end]
        if len(sl) == window:
            yield end, sl


def seed(
    tenant_id: int,
    *,
    window: int = 90,
    stride: int = 30,
    symbols: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    seeded = 0
    files = 0
    for base, path in _iter_parquet_files(symbols):
        files += 1
        try:
            df = pd.read_parquet(path)
        except Exception as e:
            logger.warning("read failed for %s: %s", path, e)
            continue
        if df.empty:
            continue
        regimes = tag_regime(df)
        for end, sl in _windows(df, window=window, stride=stride):
            try:
                vec = market_window_embedding(sl, dim=32)
                if vec.size == 0 or not vec.any():
                    continue
                anchor_ts = sl.index[-1]
                regime = str(regimes.iloc[end - 1]) if end - 1 < len(regimes) else "unknown"
                fwd = float(df["close"].iloc[end]) / float(sl["close"].iloc[-1]) - 1.0 if end < len(df) else None
                subject_id = f"{base}#{anchor_ts.isoformat()}"
                meta = {
                    "symbol_file": base,
                    "period": str(anchor_ts.date()),
                    "regime": regime,
                    "return_n": fwd,
                    "window": window,
                }
                if dry_run:
                    seeded += 1
                    continue
                upsert_market_window(
                    tenant_id=tenant_id, subject_id=subject_id, vector=vec, meta=meta,
                )
                seeded += 1
            except Exception as e:
                logger.warning("seed failed for %s window-end=%s: %s", base, end, e)
    return {"files": files, "seeded": seeded, "dry_run": dry_run}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Seed market window embeddings.")
    p.add_argument("--tenant", type=int, required=True, help="tenant_id to scope embeddings to")
    p.add_argument("--window", type=int, default=90)
    p.add_argument("--stride", type=int, default=30)
    p.add_argument("--symbols", nargs="*", default=None,
                   help="parquet basenames to include (e.g. RELIANCE.NS_1d). Default: all in DATA_CACHE_DIR.")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    started = datetime.utcnow()
    summary = seed(
        tenant_id=args.tenant,
        window=args.window,
        stride=args.stride,
        symbols=args.symbols,
        dry_run=args.dry_run,
    )
    logger.info("seed done in %.1fs: %s", (datetime.utcnow() - started).total_seconds(), summary)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
