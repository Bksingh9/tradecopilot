"""Coach agent — periodic review wrapper around AICoach.

The coach NEVER mutates risk rules or activates strategy tuning suggestions.
It only writes:
  - AIReport rows (weekly_review)
  - StrategyTuningSuggestion rows in `pending` state (must be human-accepted)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session

from app.ai.coach import get_coach
from app.audit import service as audit
from app.auth.models import User
from app.journal import journal_service as js
from app.trading.models import AIReport, RiskRule


class CoachAgent:
    def weekly_review(self, session: Session, user: User, days: int = 7) -> AIReport:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        trades = js.list_trades(session, user.id, start=start, end=end, limit=10_000)
        journal = js.list_entries(session, user.id, start=start, end=end, limit=10_000)
        rule = session.get(RiskRule, user.id) or RiskRule(
            user_id=user.id, tenant_id=user.tenant_id
        )
        content = get_coach().generate_weekly_report(trades, journal, rule)
        row = AIReport(
            user_id=user.id, tenant_id=user.tenant_id,
            kind="weekly", period_start=start, period_end=end, content=content,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        audit.record(
            session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
            action="agent.coach.weekly",
            subject_type="ai_report", subject_id=row.id,
            payload={"days": days, "trades": len(trades)},
        )

        # Best-effort embedding for RAG so future weekly reviews can retrieve.
        try:
            from app.vector_memory import text_embedding_stub, upsert_user_report
            upsert_user_report(
                tenant_id=user.tenant_id, user_id=user.id, report_id=row.id,
                vector=text_embedding_stub(content),
                meta={"period_start": str(start), "period_end": str(end)},
            )
        except Exception:
            pass

        return row
