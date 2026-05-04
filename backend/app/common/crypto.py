"""At-rest encryption helpers (Fernet) for broker tokens and similar secrets."""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.common.exceptions import TradeCopilotError
from app.config import settings


class CryptoError(TradeCopilotError):
    code = "crypto_error"


@lru_cache
def _fernet() -> Fernet:
    key = settings.secrets_fernet_key
    if not key:
        raise CryptoError("SECRETS_FERNET_KEY not configured")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:  # pragma: no cover
        raise CryptoError(f"Invalid SECRETS_FERNET_KEY: {e}") from e


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise CryptoError("Invalid ciphertext") from e
