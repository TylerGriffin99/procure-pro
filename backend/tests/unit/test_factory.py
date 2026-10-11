import functools
import logging
import uuid

import pytest
from pydantic import ValidationError

from app.clients.jev_client import JevClient
from app.clients.llm_client import LlmClient
from app.config import Settings
from app.constants import LlmProvider, MatcherName
from app.harness.definitions import HARNESS_DEFINITIONS
from app.harness.definitions.claim_parse import claim_parse_definition
from app.harness.factory import build_engine, build_matchers
from app.harness.matchers.jev import match_with_jev
from app.harness.matchers.llm import match_with_llm
from app.harness.models import HarnessType
from app.harness.schemas import JevTuning

LLM = LlmClient(provider=LlmProvider.openai, model_name="m", api_key="k")


def settings(**overrides) -> Settings:
    return Settings(secret_key="k", llm_provider="openai", llm_model="m", openai_api_key="k", **overrides)


def test_matcher_table_binds_every_collaborator_and_knob():
    table = build_matchers(
        settings(open_router_api_key="or-key", jev_confidence_floor=0.7, jev_max_concurrency=3), llm=LLM
    )

    assert set(table) == set(MatcherName)
    llm_matcher, jev_matcher = table[MatcherName.llm], table[MatcherName.jev]
    assert isinstance(llm_matcher, functools.partial) and llm_matcher.func is match_with_llm
    assert llm_matcher.keywords == {"llm": LLM}
    assert isinstance(jev_matcher, functools.partial) and jev_matcher.func is match_with_jev
    assert jev_matcher.keywords["llm"] is LLM
    assert jev_matcher.keywords["tuning"] == JevTuning(confidence_floor=0.7, max_concurrency=3)
    client = jev_matcher.keywords["client"]
    assert isinstance(client, JevClient) and client.api_key == "or-key"


def test_unset_jev_key_runs_jev_phases_on_the_llm_and_logs_once(caplog):
    with caplog.at_level(logging.WARNING, logger="app.harness.factory"):
        table = build_matchers(settings(open_router_api_key=""), llm=LLM)

    assert table[MatcherName.jev] is table[MatcherName.llm]
    assert table[MatcherName.jev].func is match_with_llm
    warnings = [r.getMessage() for r in caplog.records if "falling back to matcher=llm" in r.getMessage()]
    assert len(warnings) == 1


def test_build_engine_wires_default_matcher_and_shared_llm():
    engine = build_engine(
        settings=settings(open_router_api_key="or-key", matcher_default="jev"),
        definition=claim_parse_definition,
        session_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        db=None,
    )
    assert engine.default_matcher is MatcherName.jev
    assert engine.matchers[MatcherName.jev].keywords["llm"] is engine.llm
    assert engine.matchers[MatcherName.llm].keywords["llm"] is engine.llm


def test_harness_definitions_is_a_constant_table():
    assert HARNESS_DEFINITIONS == {HarnessType.CLAIM_PARSE: claim_parse_definition}


def test_unknown_matcher_name_is_rejected_at_settings_load():
    with pytest.raises(ValidationError, match="matcher_default"):
        Settings(secret_key="k", llm_provider="openai", llm_model="m", matcher_default="nope")
