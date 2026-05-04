"""Embedding builders.

`market_window_embedding(df, dim)` reduces a normalized OHLCV window to a fixed
`dim`-vector via sklearn `TruncatedSVD` if the window is large enough, otherwise
falls back to padded normalized features.

`text_embedding_stub(s, dim)` is a deterministic hash-bucket embedding so tests
are stable. Production should swap in a real text embedding model behind the
same signature; a separate worker is recommended for that work.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd


# --- Market window --------------------------------------------------------
def market_window_embedding(df: pd.DataFrame, dim: int = 32) -> np.ndarray:
    """Reduce the trailing portion of `df` to a `dim`-vector.

    We compute log-returns over (open, high, low, close) and intraday range,
    z-score them, then either run TruncatedSVD (if long enough) or pad to `dim`.
    The output is unit-norm so cosine similarity == dot product.
    """
    if df is None or df.empty:
        return np.zeros(dim, dtype=np.float64)

    win = df.tail(120).copy()
    eps = 1e-9
    feats = pd.DataFrame(index=win.index)
    feats["log_close"] = np.log(win["close"].clip(lower=eps)).diff()
    feats["log_high"] = np.log(win["high"].clip(lower=eps)).diff()
    feats["log_low"] = np.log(win["low"].clip(lower=eps)).diff()
    feats["range_pct"] = (win["high"] - win["low"]) / win["close"].replace(0, np.nan)
    feats = feats.fillna(0.0)
    arr = feats.values.astype(np.float64)
    if arr.size == 0:
        return np.zeros(dim, dtype=np.float64)

    mu = arr.mean(axis=0, keepdims=True)
    sd = arr.std(axis=0, keepdims=True) + 1e-9
    arr = (arr - mu) / sd

    flat = arr.reshape(1, -1)
    n_components = min(dim, flat.shape[1] - 1)
    if n_components >= 2:
        try:
            from sklearn.decomposition import TruncatedSVD

            # SVD over a "fattened" matrix: stack diagonal & moments to give SVD signal.
            stacked = np.vstack([
                arr.mean(axis=0),
                arr.std(axis=0),
                arr.min(axis=0),
                arr.max(axis=0),
                np.percentile(arr, 25, axis=0),
                np.percentile(arr, 75, axis=0),
            ])
            n_comp = min(dim, min(stacked.shape) - 1) or 1
            svd = TruncatedSVD(n_components=max(n_comp, 1), random_state=0)
            v = svd.fit_transform(stacked)[0]
            v = _pad_or_truncate(v, dim)
        except Exception:
            v = _pad_or_truncate(flat[0], dim)
    else:
        v = _pad_or_truncate(flat[0], dim)
    return _l2_norm(v)


def _pad_or_truncate(v: np.ndarray, dim: int) -> np.ndarray:
    if v.shape[0] >= dim:
        return v[:dim].astype(np.float64)
    out = np.zeros(dim, dtype=np.float64)
    out[: v.shape[0]] = v.astype(np.float64)
    return out


def _l2_norm(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n == 0 or math.isnan(n):
        return v.astype(np.float64)
    return (v / n).astype(np.float64)


# --- Text (stub) ----------------------------------------------------------
def text_embedding_stub(s: str, dim: int = 384) -> np.ndarray:
    """Deterministic hash-bucket embedding. CLEARLY a stub — swap in a real
    text embedding service via a separate worker for production."""
    if not s:
        return np.zeros(dim, dtype=np.float64)
    out = np.zeros(dim, dtype=np.float64)
    # Tokenise loosely on whitespace; hash each token into multiple buckets.
    for i, tok in enumerate(s.lower().split()[:256]):
        h = hashlib.sha1(tok.encode()).digest()
        for j, b in enumerate(h[:8]):
            out[(int.from_bytes(h[j : j + 1], "big") + i) % dim] += (b / 255.0) - 0.5
    return _l2_norm(out)
