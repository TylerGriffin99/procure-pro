from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.harness.matchers.jev import JevMatcher
from app.harness.matchers.llm import LlmMatcher
from app.harness.schemas import MatchOutcome


@runtime_checkable
class DecisionMatcher(Protocol):
    name: str

    async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome: ...


def get_matcher(name: str) -> DecisionMatcher:
    """Resolve a matcher by name."""
    if name == "llm":
        return LlmMatcher()
    if name == "jev":
        return JevMatcher()
    raise ValueError(f"Unknown matcher: {name!r}. Use 'llm' or 'jev'.")
