from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)


class Settings(BaseSettings):
    openrouter_key: str | None = Field(default=None, alias="OPENROUTER_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL")
    openrouter_api_base: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_API_BASE")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    bedrock_model_id: str = Field(default="us.anthropic.claude-haiku-4-5-20251001-v1:0", alias="BEDROCK_MODEL_ID")
    storage_dir: Path = Path(__file__).resolve().parents[1] / "storage"

    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    base = (settings.openrouter_api_base or "").split("#", 1)[0].strip().rstrip("/")
    if base in {"https://api.openrouter.ai", "https://openrouter.ai"}:
        base = "https://openrouter.ai/api/v1"
    elif base and not base.endswith("/api/v1"):
        base = f"{base}/api/v1"
    settings.openrouter_api_base = base or "https://openrouter.ai/api/v1"
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
