"""Orchestrator — chains Analyst → Strategy → Risk → Execution per (user, symbol).

Honors the user's `autonomy_mode` and emits one AuditEvent per stage transition.
Never bypasses the kill switch or risk caps; refuses to run in `full_auto` unless
the user is paper-qualified AND has consented.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session

from app.agents.analyst import AnalystAgent
from app.agents.execution_agent import ExecutionAgent
from app.agents.models import CycleReport, ExecutionResult, StageEvent
from app.agents.risk_agent import RiskAgent
from app.agents.strategy import StrategyAgent
from app.audit import service as audit
from app.auth.models import User
from app.common.exceptions import PermissionDenied


class Orchestrator:
    def __init__(self) -> None:
        self.analyst = AnalystAgent()
        self.strategy = StrategyAgent()
        self.risk = RiskAgent()
        self.executor = ExecutionAgent()

    def run_cycle(
        self,
        session: Session,
        user: User,
        symbols: list[str],
        *,
        timeframe: str = "1d",
        broker: str = "alpaca",
        exchange_hint: Optional[str] = None,
    ) -> CycleReport:
        mode = user.autonomy_mode
        if mode == "full_auto":
            if not user.paper_qualified_at:
                raise PermissionDenied("full_auto requires paper qualification")
            if not user.consent_full_auto:
                raise PermissionDenied("full_auto requires explicit consent")

        report = CycleReport(
            user_id=user.id, tenant_id=user.tenant_id, mode=mode,
            started_at=datetime.utcnow(),
        )
        audit.record(
            session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
            action="agent.cycle.start",
            subject_type="cycle", subject_id=None,
            payload={"symbols": symbols, "mode": mode, "timeframe": timeframe},
        )

        for sym in symbols:
            try:
                signal = self.analyst.assess(sym, timeframe=timeframe, exchange_hint=exchange_hint)
                report.stages.append(StageEvent(
                    stage="analyst", ok=True,
                    summary=f"{sym}: p_up={signal.p_up:.2f} regime={signal.regime}",
                    payload={"symbol": sym},
                ))
            except Exception as e:
                report.stages.append(StageEvent(
                    stage="analyst", ok=False, summary=f"{sym}: {e}",
                ))
                continue

            cands = self.strategy.propose(signal, user)
            report.stages.append(StageEvent(
                stage="strategy", ok=True,
                summary=f"{sym}: {len(cands)} candidate(s)",
                payload={"symbol": sym, "n": len(cands)},
            ))
            if not cands:
                continue

            for cand in cands:
                decision = self.risk.review(session, cand, user)
                report.stages.append(StageEvent(
                    stage="risk", ok=decision.action != "reject",
                    summary=f"{sym}: {decision.action} ({decision.final_qty}) — {decision.reason[:80]}",
                    payload={"symbol": sym, "action": decision.action, "qty": decision.final_qty},
                ))

                result: ExecutionResult = self.executor.run(
                    session, decision, user, mode=mode, broker=broker
                )
                report.results.append(result)
                report.stages.append(StageEvent(
                    stage="execution", ok=result.status in {"placed", "proposed"},
                    summary=f"{sym}: {result.status}",
                    payload={"symbol": sym, "status": result.status},
                ))

        report.finished_at = datetime.utcnow()
        audit.record(
            session, tenant_id=user.tenant_id, user_id=user.id, actor="agent",
            action="agent.cycle.end",
            subject_type="cycle",
            payload={"results": len(report.results), "mode": mode},
        )
        return report
