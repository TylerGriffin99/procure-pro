import functools
import logging
from collections.abc import Callable, Mapping

from app.clients.jev_client import JevClient
from app.clients.llm_client import LlmClient
from app.config import Settings
from app.constants.enums import MatcherName
from app.harness.engine import HarnessEngine
from app.harness.matchers.jev import match_with_jev
from app.harness.matchers.llm import match_with_llm
from app.harness.models import Matcher
from app.harness.schemas import JevTuning

logger = logging.getLogger(__name__)

EngineBuilder = Callable[..., HarnessEngine]


def build_matchers(settings: Settings, *, llm: LlmClient) -> dict[MatcherName, Matcher]:
    llm_matcher = functools.partial(match_with_llm, llm=llm)
    if not settings.open_router_api_key:
        logger.warning(
            "matcher=jev requested but open_router_api_key is unset; "
            "falling back to matcher=llm for every matcher=jev phase."
        )
        return {MatcherName.llm: llm_matcher, MatcherName.jev: llm_matcher}
    tuning = JevTuning(confidence_floor=settings.jev_confidence_floor, max_concurrency=settings.jev_max_concurrency)
    jev_matcher = functools.partial(match_with_jev, client=JevClient.from_settings(settings), llm=llm, tuning=tuning)
    return {MatcherName.llm: llm_matcher, MatcherName.jev: jev_matcher}


def engine_builder(*, settings: Settings, llm: LlmClient, matchers: Mapping[MatcherName, Matcher]) -> EngineBuilder:
    return functools.partial(HarnessEngine, llm=llm, matchers=matchers, default_matcher=settings.matcher_default)
