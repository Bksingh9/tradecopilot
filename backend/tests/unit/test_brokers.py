from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.brokers.alpaca_client import AlpacaClient
from app.brokers.models import OrderRequest
from app.brokers.upstox_client import UpstoxClient
from app.common.exceptions import BrokerError


# --- Alpaca: fully mock the underlying httpx call -----------------------------
class _DummyResp:
    def __init__(self, json_payload, status_code=200):
        self._json = json_payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._json


def test_alpaca_place_order_happy(monkeypatch):
    client = AlpacaClient()
    client.api_key = "k"
    client.api_secret = "s"

    def fake_post(self, url, json=None, headers=None, **kw):
        return _DummyResp({"id": "abc-123", "status": "accepted",
                           "filled_qty": "0", "filled_avg_price": "0"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    res = client.place_order(OrderRequest(symbol="AAPL", side="BUY", qty=1, paper=True))
    assert res.broker_order_id == "abc-123"


def test_alpaca_missing_keys_raises():
    client = AlpacaClient()
    client.api_key = ""
    client.api_secret = ""
    with pytest.raises(BrokerError):
        client.place_order(OrderRequest(symbol="AAPL", side="BUY", qty=1, paper=True))


# --- Upstox login URL is deterministic, no network needed --------------------
def test_upstox_login_url():
    c = UpstoxClient()
    c.client_id = "cid"
    url = c.login_url(state="x")
    assert "client_id=cid" in url
    assert "state=x" in url


def test_upstox_missing_token_raises():
    c = UpstoxClient(access_token=None)
    with pytest.raises(BrokerError):
        c.get_positions()
