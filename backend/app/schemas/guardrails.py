from app.constants.enums import ViolationCategory
from app.schemas.base import StrictModel


class Violation(StrictModel):
    category: ViolationCategory
    snippet: str  # the matched text, for the server-side log
