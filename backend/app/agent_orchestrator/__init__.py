"""ML + RAG-aware decision orchestrator.

Wraps the existing agents (`app.agents.*`) with a richer context loop that
pulls ML predictions + similar historical windows (RAG) before letting the
Strategy / Risk / Execution agents act.

Public surface:
    run_decision_cycle(session, user, symbols, *, mode=None, broker="alpaca",
                       exchange_hint=None) -> list[DecisionOutcome]
"""
from app.agent_orchestrator.models import DecisionContext, DecisionProposal, DecisionOutcome
from app.agent_orchestrator.orchestrator import run_decision_cycle

__all__ = ["DecisionContext", "DecisionProposal", "DecisionOutcome", "run_decision_cycle"]
