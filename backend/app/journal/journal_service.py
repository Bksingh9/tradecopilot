"""CRUD for JournalEntry — always scoped by user_id (and tenant_id implicitly)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.auth.models import User
from app.common.exceptions import NotFound, PermissionDenied
from app.trading.models import JournalEntry, Trade


def add_entry(
    session: Session,
    user: User,
    *,
    trade_id: Optional[int] = None,
    setup: Optional[str] = None,
    emotion_tag: Optional[str] = None,
    screenshot_url: Optional[str] = None,
    notes: Optional[str] = None,
) -> JournalEntry:
    if trade_id is not None:
        trade = session.get(Trade, trade_id)
        if not trade:
            raise NotFound("Trade not found")
        if trade.user_id != user.id or trade.tenant_id != user.tenant_id:
            raise PermissionDenied("Trade not yours")
    entry = JournalEntry(
        user_id=user.id,
        tenant_id=user.tenant_id,
        trade_id=trade_id,
        setup=setup,
        emotion_tag=emotion_tag,
        screenshot_url=screenshot_url,
        notes=notes,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    # Best-effort embedding for RAG. Never block the request on failure.
    try:
        from app.vector_memory import text_embedding_stub, upsert_user_journal
        text = " ".join(filter(None, [setup, emotion_tag, notes]))
        if text:
            upsert_user_journal(
                tenant_id=user.tenant_id, user_id=user.id, entry_id=entry.id,
                vector=text_embedding_stub(text),
                meta={"setup": setup, "emotion": emotion_tag, "trade_id": trade_id},
            )
    except Exception:
        pass

    return entry


def list_entries(
    session: Session,
    user_id: int,
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 200,
) -> list[JournalEntry]:
    q = select(JournalEntry).where(JournalEntry.user_id == user_id)
    if start:
        q = q.where(JournalEntry.created_at >= start)
    if end:
        q = q.where(JournalEntry.created_at <= end)
    q = q.order_by(JournalEntry.created_at.desc()).limit(limit)
    return list(session.exec(q).all())


def list_trades(
    session: Session,
    user_id: int,
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    status: Optional[str] = None,
    strategy: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 500,
) -> list[Trade]:
    q = select(Trade).where(Trade.user_id == user_id)
    if start:
        q = q.where(Trade.opened_at >= start)
    if end:
        q = q.where(Trade.opened_at <= end)
    if status:
        q = q.where(Trade.status == status)
    if strategy:
        q = q.where(Trade.strategy == strategy)
    if symbol:
        q = q.where(Trade.symbol == symbol.upper())
    q = q.order_by(Trade.opened_at.desc()).limit(limit)
    return list(session.exec(q).all())
