"""Alias package — re-exports journal CRUD and analytics."""
from app.journal import journal_service, analytics  # noqa: F401
from app.journal.journal_service import add_entry, list_entries, list_trades  # noqa: F401
from app.journal.analytics import (  # noqa: F401
    summary, by_symbol, by_strategy, r_distribution,
    by_hour_of_day, best_worst_hour, streaks, aggregate_overview_anonymized,
)
