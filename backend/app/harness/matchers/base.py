from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class MatchOutcome:
    """Result of a matcher run: the typed list + its serialized form + usage."""

    output: list[Any]          # list[WbsMatch] or list[VpsMatch]
    output_json: str           # bare JSON array matching the phase output_schema
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    fell_back: int = 0         # items that fell back after a Jev failure
    residue: int = 0           # items routed to the LLM (none/low-confidence)


@runtime_checkable
class DecisionMatcher(Protocol):
    name: str

    async def match(self, *, phase_def, db, project_id, session_id) -> MatchOutcome:
        ...


def get_matcher(name: str) -> DecisionMatcher:
    """Resolve a matcher by name. Imports are local to avoid import cycles."""
    if name == "llm":
        from app.harness.matchers.llm import LlmMatcher
        return LlmMatcher()
    if name == "jev":
        from app.harness.matchers.jev import JevMatcher
        return JevMatcher()
    raise ValueError(f"Unknown matcher: {name!r}. Use 'llm' or 'jev'.")
