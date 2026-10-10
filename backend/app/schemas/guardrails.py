from app.schemas.base import StrictModel


class Violation(StrictModel):
    category: str  # "prompt_injection" | "code"
    snippet: str  # the matched text, for the server-side log
