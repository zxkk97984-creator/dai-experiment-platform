from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DAI_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "DAI Experiment Platform API"
    environment: str = "development"
    database_url: str = "mysql+pymysql://dai:dai_password@localhost:3306/dai_platform"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = Field(default="change-me-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    jupyter_base_url: str = "http://localhost:8888"
    judge_queue_name: str = "judge:queue"
    judge_image: str = "dai-judge-python:latest"
    judge_use_docker: bool = True
    judge_timeout_seconds: int = 10
    judge_memory_limit_mb: int = 256
    judge_cpu_limit: float = 1.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
