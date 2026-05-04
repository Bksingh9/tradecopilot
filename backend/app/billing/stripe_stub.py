"""Stripe integration stub. The real impl will live behind the same interface."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from app.billing.models import Subscription
from app.config import settings


def create_checkout_session(user_id: int, plan: str, success_url: str, cancel_url: str) -> str:
    """Return a Stripe Checkout URL. Stubbed: just echoes a fake URL."""
    if not settings.stripe_secret_key:
        return f"https://stripe.example/checkout?stub=1&plan={plan}&user={user_id}"
    # Real impl:
    # import stripe
    # stripe.api_key = settings.stripe_secret_key
    # session = stripe.checkout.Session.create(...)
    # return session.url
    return f"https://stripe.example/checkout?plan={plan}&user={user_id}"


def upsert_subscription(
    session: Session,
    user_id: int,
    *,
    plan: str = "free",
    status: str = "active",
    provider_customer_id: Optional[str] = None,
    provider_subscription_id: Optional[str] = None,
) -> Subscription:
    sub = session.get(Subscription, user_id) if False else None
    # SQLModel default PK is id; we need to query by user_id:
    from sqlmodel import select
    sub = session.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
    if not sub:
        sub = Subscription(user_id=user_id)
    sub.plan = plan
    sub.status = status
    sub.provider_customer_id = provider_customer_id
    sub.provider_subscription_id = provider_subscription_id
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def handle_webhook(payload: dict, signature: str) -> dict:
    """Verify + handle a Stripe webhook. Stubbed."""
    # Real impl uses stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret).
    return {"received": True, "stub": True}
