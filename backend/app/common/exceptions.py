"""Domain-level exceptions (mapped to HTTP errors at the API layer)."""
from __future__ import annotations


class TradeCopilotError(Exception):
    """Base class for all app exceptions."""

    http_status: int = 400
    code: str = "trade_copilot_error"


class AuthError(TradeCopilotError):
    http_status = 401
    code = "auth_error"


class PermissionDenied(TradeCopilotError):
    http_status = 403
    code = "permission_denied"


class NotFound(TradeCopilotError):
    http_status = 404
    code = "not_found"


class ValidationError(TradeCopilotError):
    http_status = 422
    code = "validation_error"


class RiskRuleViolation(TradeCopilotError):
    """Raised by trading.risk when an order would violate a user's risk config."""

    http_status = 409
    code = "risk_rule_violation"


class BrokerError(TradeCopilotError):
    """Wraps any error coming from a broker SDK / API."""

    http_status = 502
    code = "broker_error"


class DataSourceError(TradeCopilotError):
    http_status = 502
    code = "data_source_error"
