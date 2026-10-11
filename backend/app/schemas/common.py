"""Small value types shared across layers."""

from typing import Annotated

from pydantic import Field

from app.schemas.base import StrictModel

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
ItemIndex = Annotated[int, Field(ge=0)]


class RetryPolicy(StrictModel):
    """Bounded exponential backoff: ``base_delay * 2**attempt`` plus up to that much jitter."""

    max_attempts: int = Field(default=4, ge=1)
    base_delay: float = Field(default=0.5, ge=0.0)
