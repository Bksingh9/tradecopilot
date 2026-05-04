"""Structured-ish logging setup. Never logs secrets or full PII payloads."""
from __future__ import annotations

import logging
import re
import sys
from typing import Any

from app.config import settings

# Patterns we will redact if they ever leak into log records.
_SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key|secret|token|password|fernet)[\"'=:\s]+([A-Za-z0-9_\-./+=]{6,})", re.I),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-.]+", re.I),
]


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        for pat in _SECRET_PATTERNS:
            msg = pat.sub(lambda m: f"{m.group(1) if m.lastindex else 'secret'}=***REDACTED***", msg)
        record.msg = msg
        record.args = ()
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s")
    )
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def safe_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Log a structured event, dropping known-secret keys."""
    drop = {"password", "api_key", "api_secret", "access_token", "fernet_key"}
    safe = {k: ("***" if k in drop else v) for k, v in fields.items()}
    logger.log(level, "%s %s", event, safe)
