from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = next(
    (
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pnpm-workspace.yaml").is_file()
    ),
    Path(__file__).resolve().parents[1],
)
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_DIMENSIONS = 4096
EMBEDDING_INPUT_PRICE = 0.01
EMBEDDING_QUERY_INSTRUCTION = (
    "Given a question, retrieve relevant document passages that answer it."
)
EMBEDDING_FINGERPRINT = f"openrouter:{EMBEDDING_MODEL}:4096:cosine:qwen-query-v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TAMPAK_", env_file=ROOT / ".env", extra="ignore")
    env: str = "development"
    database_url: SecretStr
    migration_database_url: SecretStr | None = None
    app_db_password: SecretStr = SecretStr("")
    master_key: SecretStr
    admin_username: str = "admin"
    admin_password: SecretStr = SecretStr("")
    data_dir: Path = ROOT / "runtime"
    web_origin: str = "http://localhost:3010"
    api_url: str = "http://127.0.0.1:8100"
    allow_local_providers: bool = True
    openrouter_api_key: SecretStr = SecretStr("")
    embedding_batch_size: int = Field(default=12, ge=1, le=12)
    embedding_interval_seconds: float = Field(default=0.2, ge=0, le=60)
    chat_base_url: str = "https://openrouter.ai/api/v1"
    chat_model: str = ""
    chat_api_key: SecretStr = SecretStr("")
    vision_model: str = ""
    vision_api_key: SecretStr = SecretStr("")
    guest_bot_limit: int = 3
    upload_max_bytes: int = 10 * 1024 * 1024
    guest_storage_bytes: int = 50 * 1024 * 1024
    source_page_limit: int = 50
    guest_page_limit: int = 100
    guest_turn_limit: int = 30
    guest_file_limit: int = 5
    guest_model_call_limit: int = 120
    guest_token_limit: int = 200000
    processing_timeout: int = 180
    provider_timeout: int = 90

    @property
    def storage(self) -> Path:
        path = (self.data_dir if self.data_dir.is_absolute() else ROOT / self.data_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def settings() -> Settings:
    return Settings()
