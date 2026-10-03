"""Guards the shipped claim_parse wiring: phases 4 & 5 run through JevMatcher."""
import pytest

from app.harness.definitions.claim_parse import claim_parse_definition
from app.harness.models import PhaseType
from app.harness.schemas import VpsMatch, WbsMatch


def _phase(name):
    return next(p for p in claim_parse_definition.phases if p.name == name)


@pytest.mark.parametrize(
    "name,schema",
    [("WBS Categorisation", list[WbsMatch]), ("Variation Matching", list[VpsMatch])],
)
def test_matching_phases_run_through_jev(name, schema):
    phase = _phase(name)
    assert phase.phase_type == PhaseType.LLM_BATCH_AGENTS
    assert phase.matcher == "jev"
    assert phase.output_schema == schema
    assert phase.context_loaders  # LLM fallback still needs its context
