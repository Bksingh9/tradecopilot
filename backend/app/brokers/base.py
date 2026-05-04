"""Abstract broker interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.brokers.models import BrokerName, Order, OrderRequest, OrderResult, Position


class BrokerClient(ABC):
    """All broker connectors implement this minimal interface."""

    name: BrokerName

    # --- Auth / connection lifecycle -----------------------------------------
    @abstractmethod
    def login_url(self, state: Optional[str] = None) -> str:
        """Return the URL the user must visit to authorize."""

    @abstractmethod
    def exchange_code(self, code_or_request_token: str) -> str:
        """Exchange the broker-issued code/request_token for an access_token."""

    # --- Trading -------------------------------------------------------------
    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResult: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...

    @abstractmethod
    def get_orders(self, status_filter: Optional[str] = None) -> list[Order]: ...
