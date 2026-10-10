"""Pydantic base for internal value types."""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Internal value types: no unknown fields, immutable, validated on construction.

    API request/response DTOs keep pydantic defaults; LLM-output schemas keep
    ``extra="ignore"``. Use this for everything else that used to be a dataclass.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
