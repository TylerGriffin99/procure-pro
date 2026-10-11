from __future__ import annotations

from typing import Protocol, assert_never

from app.clients.llm_client import LlmClient
from app.constants.enums import MatcherName
from app.harness.matchers.jev import JevMatcher
from app.harness.matchers.llm import LlmMatcher
from app.harness.schemas import MatchOutcome


class DecisionMatcher(Protocol):
    async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome: ...


def get_matcher(name: MatcherName, *, llm: LlmClient) -> DecisionMatcher:
    """Resolve a matcher by name."""
    match name:
        case MatcherName.llm:
            return LlmMatcher(llm=llm)
        case MatcherName.jev:
            return JevMatcher(llm=llm)
        case _:
            assert_never(name)
