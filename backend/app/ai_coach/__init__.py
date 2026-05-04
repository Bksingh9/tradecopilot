"""Alias package — re-exports the AI coach surface."""
from app.ai.coach import AICoach, FakeCoach, ExternalQueueCoach, get_coach  # noqa: F401
from app.ai.prompts import (  # noqa: F401
    SYSTEM_PROMPT, render_weekly_report, render_trade_comment, render_tuning_review,
)
from app.agents.coach_agent import CoachAgent  # noqa: F401
