from typing import Final

from app.harness.definitions.claim_parse import claim_parse_definition
from app.harness.models import HarnessDefinition, HarnessType

__all__ = ["HARNESS_DEFINITIONS"]

HARNESS_DEFINITIONS: Final[dict[HarnessType, HarnessDefinition]] = {HarnessType.CLAIM_PARSE: claim_parse_definition}
