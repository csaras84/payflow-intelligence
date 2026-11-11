from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project-root .env (payflow-intelligence/.env). Loaded into os.environ so code that
# uses os.getenv (graph nodes, langchain-anthropic) sees the same values as Settings,
# regardless of which folder uvicorn is started from.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_FILE)

PAYPAL_URLS = {
    "SANDBOX": "https://api-m.sandbox.paypal.com",
    "LIVE": "https://api-m.paypal.com",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # PayPal
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_environment: Literal["SANDBOX", "LIVE"] = "SANDBOX"

    # LLM (Anthropic Claude)
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"

    # Database
    database_url: str = "sqlite:///./payflow.db"

    # App
    cors_origins: str = "http://localhost:5173"
    liquidity_threshold: float = 1000.0

    @property
    def paypal_base_url(self) -> str:
        return PAYPAL_URLS[self.paypal_environment]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
