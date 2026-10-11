import functools

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

from app.constants.enums import LlmProvider, MatcherName
from app.constants.values import PROVIDER_TABLE


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://claimreview:claimreview_dev@localhost:6000/claimreview"

    @model_validator(mode="after")
    def normalize_database_url(self):
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self

    secret_key: str
    access_token_expire_minutes: int = 60 * 24

    llm_provider: LlmProvider
    llm_model: str

    @field_validator("llm_provider", mode="before")
    @classmethod
    def lowercase_provider(cls, v: object) -> object:
        return v.lower() if isinstance(v, str) else v

    # API keys — only the key for the configured provider is required
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    open_router_api_key: str = ""
    deepseek_api_key: str = ""

    @model_validator(mode="after")
    def require_provider_key(self):
        _, key_field = PROVIDER_TABLE[self.llm_provider]
        if not getattr(self, key_field):
            raise ValueError(f"{key_field.upper()} must be set when LLM_PROVIDER={self.llm_provider.value}")
        return self

    matcher_default: MatcherName = MatcherName.llm
    jev_model: str = "typesafe/jev-1.13"
    jev_decisions_url: str = "https://openrouter.ai/api/alpha/decisions"
    jev_max_concurrency: int = 8
    jev_confidence_floor: float = 0.6

    @field_validator(
        "anthropic_api_key",
        "openai_api_key",
        "open_router_api_key",
        "deepseek_api_key",
        "jev_decisions_url",
        mode="before",
    )
    @classmethod
    def strip_whitespace(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    # API versioning: every router mounts under `/api/v{api_version}`; /health stays unversioned.
    api_version: int = 1

    @property
    def api_prefix(self) -> str:
        return f"/api/v{self.api_version}"

    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "extra": "ignore", "hide_input_in_errors": True}


@functools.cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]  # required fields come from env/.env


# Import-time alias (database engine, oauth2 tokenUrl, router prefix); the same instance get_settings() provides.
settings = get_settings()
