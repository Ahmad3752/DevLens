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
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_service_role_key: str | None = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    devlens_redis_url: str | None = Field(default=None, alias="DEVLENS_REDIS_URL")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    bedrock_model_id: str = Field(default="us.anthropic.claude-haiku-4-5-20251001-v1:0", alias="BEDROCK_MODEL_ID")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")
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
    if settings.supabase_url:
        settings.supabase_url = settings.supabase_url.strip().rstrip("/")
    if settings.devlens_redis_url:
        settings.devlens_redis_url = settings.devlens_redis_url.strip()
    if settings.redis_url:
        settings.redis_url = settings.redis_url.strip()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
