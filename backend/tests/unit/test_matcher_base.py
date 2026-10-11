import pytest
from pydantic import ValidationError

from app.config import Settings
from app.constants import MatcherName
from app.harness.matchers.base import get_matcher
from app.harness.matchers.jev import JevMatcher
from app.harness.matchers.llm import LlmMatcher
from app.harness.schemas import MatchOutcome


def test_match_outcome_defaults():
    out = MatchOutcome(output=[], output_json="[]")
    assert out.input_tokens == 0
    assert out.output_tokens == 0


@pytest.mark.parametrize(("name", "cls"), [(MatcherName.llm, LlmMatcher), (MatcherName.jev, JevMatcher)])
def test_get_matcher_resolves_each_name(name, cls):
    assert isinstance(get_matcher(name), cls)


def test_unknown_matcher_name_is_rejected_at_settings_load():
    with pytest.raises(ValidationError, match="matcher_default"):
        Settings(secret_key="k", llm_provider="openai", llm_model="m", matcher_default="nope")
