from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://claimreview:claimreview_dev@localhost:6000/claimreview"

    @model_validator(mode="after")
    def normalize_database_url(self):
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self
    secret_key: str
    access_token_expire_minutes: int = 60 * 24

    # LLM provider: "anthropic", "openai", "openrouter", or "deepseek"
    llm_provider: str
    llm_model: str

    # API keys — only the key for the configured provider is required
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    open_router_api_key: str = ""
    deepseek_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
