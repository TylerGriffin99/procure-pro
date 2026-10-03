import pytest
from app.harness.matchers.base import MatchOutcome, get_matcher


def test_match_outcome_defaults():
    out = MatchOutcome(output=[], output_json="[]")
    assert out.input_tokens == 0
    assert out.output_tokens == 0
    assert out.cost_usd is None


def test_get_matcher_unknown_raises():
    with pytest.raises(ValueError, match="Unknown matcher"):
        get_matcher("nope")
