"""Agentic workflow.

Pipeline (one cycle per user/symbol):

    Analyst.assess(symbol, tf)
        → AnalystSignal (technical features + ML-stub probability + sentiment)
    Strategy.propose(signal, user)
        → list[CandidateTrade]
    Risk.review(candidate, user)
        → RiskDecision (approve, scale_down, reject; never loosens caps)
    Execution.run(decision, user, mode)
        → ExecutionResult (placed | proposed | skipped, with audit_event_id)

Each stage writes one AuditEvent. The orchestrator never bypasses
`app.trading.risk` or the kill switch.
"""
from app.agents.models import (
    AnalystSignal, CandidateTrade, RiskDecision, ExecutionResult, CycleReport,
    AutonomyMode,
)

__all__ = [
    "AnalystSignal", "CandidateTrade", "RiskDecision",
    "ExecutionResult", "CycleReport", "AutonomyMode",
]
