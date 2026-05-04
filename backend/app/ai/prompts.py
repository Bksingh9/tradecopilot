"""Centralized prompt templates.

These prompts are designed for an external LLM orchestrator (worker) that calls
Claude or similar. The backend never makes outbound LLM calls in this module.

All prompts target a *retail Indian trader* (rupee-denominated, NSE/BSE focus),
avoid financial advice, and use educational framing. Output structures are kept
strict so the UI can render results without a parser.
"""
from __future__ import annotations

from string import Template

# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are TradeCopilot, a calm, evidence-based trading coach for an Indian retail
trader (NSE/BSE equities). You speak plainly, like a senior friend reviewing
the trader's week. You NEVER give financial advice or recommend specific trades.

Strict rules:
- Educational framing only. Add a short disclaimer at the end of every response.
- Always cite specific numbers from the data block: trade ids, dates, P&L, R-multiples.
- Identify *behavioral* mistakes first (overtrading, revenge trading, oversizing,
  ignoring stops, FOMO entries). Be specific, not generic.
- Suggest *process* improvements, not market predictions.
- Never propose changes to source code, broker integrations, or risk rules
  themselves. You may only propose *parameter* tweaks within an existing strategy.
- Indian rupees (₹) for INR symbols, USD ($) for US symbols.
- Be concise. Prefer short paragraphs and a tight checklist over long prose.
"""


# ---------------------------------------------------------------------------
WEEKLY_REPORT_TEMPLATE = Template(
    """\
You are reviewing a single trader's last 7 trading days.

DATA (JSON, anonymized — no PII):
$payload

Produce the report in this exact structure (Markdown):

### Snapshot
- Total P&L, win rate, # trades, avg R, biggest win / biggest loss.

### What worked
- 2-3 concrete observations citing specific trades or strategies.

### What hurt
- Behavioral patterns observed in this week's trades and journal notes.
  Common patterns to scan for: overtrading on a single stock, revenge trading
  after a loss, widening stops, sizing up after wins, late entries chasing.

### Process improvements (next week)
- 3 specific, checkable items the trader should do differently. Each item
  should be a single sentence the trader can paste into their plan.

### Coach note
- One short paragraph in plain language (think: "what would a calm friend say?").

End with: "Educational use only. Not financial advice."
"""
)


# ---------------------------------------------------------------------------
TRADE_COMMENT_TEMPLATE = Template(
    """\
You are commenting on a single trade.

TRADE (JSON):
$trade

CONTEXT (JSON, e.g. recent journal notes, risk settings):
$context

Respond in this structure:
1. **Setup quality (1-5)**: brief why.
2. **Risk hygiene**: was the position size and stop consistent with the user's risk rule?
3. **Behavioral note**: any sign of fomo / revenge / overconfidence based on context?
4. **What to do better next time** (1 sentence).

End with: "Educational use only. Not financial advice."
"""
)


# ---------------------------------------------------------------------------
# Tuning review — STRICTLY parameter-only suggestions.
# ---------------------------------------------------------------------------
TUNING_REVIEW_TEMPLATE = Template(
    """\
You are reviewing the recent performance and risk metrics for a single user
and proposing *parameter* tweaks for an existing strategy.

DATA (JSON, anonymized):
$payload

You MUST:
- Output strictly valid JSON, no markdown fences, no extra prose.
- Only suggest changes to fields already present in `current_params`.
- Stay within these guardrails (you must not propose values outside these bounds):
  $guardrails
- Express *why* in plain language (1-2 sentences) the trader can read.
- NEVER propose code changes, new strategies, looser risk rules, or higher leverage.

JSON schema (return exactly this shape):

{
  "strategy": "<strategy_name>",
  "suggested_params": { ... only keys from current_params ... },
  "rationale": "<plain-language reason in 1-2 sentences>",
  "disclaimer": "Educational use only. Not financial advice."
}

If the data does not warrant a change, return suggested_params equal to current_params.
"""
)


def render_weekly_report(payload_json: str) -> str:
    return WEEKLY_REPORT_TEMPLATE.safe_substitute(payload=payload_json)


def render_trade_comment(trade_json: str, context_json: str) -> str:
    return TRADE_COMMENT_TEMPLATE.safe_substitute(trade=trade_json, context=context_json)


def render_tuning_review(payload_json: str, guardrails_json: str) -> str:
    return TUNING_REVIEW_TEMPLATE.safe_substitute(payload=payload_json, guardrails=guardrails_json)


# ---------------------------------------------------------------------------
# Decision review — consumed by the ML+RAG agent_orchestrator. The LLM is
# expected to *cite* numerical ML scores, reference retrieved similar regimes,
# and consult `user_behavior_profile` rather than speculating.
# ---------------------------------------------------------------------------
DECISION_REVIEW_TEMPLATE = Template(
    """\
You are reviewing a single decision cycle for one trader.

DATA (JSON, anonymized):
$payload

You MUST:
- Cite ML scores numerically (prob_up, risk_score, model_version) at least once.
- Reference at least one retrieved similar regime by `score` and `regime` if any
  are present in `similar_windows`.
- Consult `user_behavior_profile.tendencies` and call out specific flags that
  are TRUE; ignore flags that are FALSE.
- Propose realistic *rules* and parameter tweaks (e.g. "skip new entries in the
  first 15 minutes after open"). Do NOT predict the future; do NOT promise outcomes.
- Output strictly valid JSON, no markdown fences, no extra prose.

JSON schema (return exactly this shape):

{
  "summary": "<2-sentence plain-language read of the situation>",
  "rules": [
    "<short, checkable process rule>",
    "..."
  ],
  "parameter_tweaks": [
    {"key": "<param>", "current": <value>, "suggested": <value>, "why": "<short>"}
  ],
  "behavior_notes": "<1-2 sentences about the user_behavior_profile flags>",
  "disclaimer": "Educational use only. Not financial advice."
}
"""
)


def render_decision_review(payload_json: str) -> str:
    return DECISION_REVIEW_TEMPLATE.safe_substitute(payload=payload_json)
