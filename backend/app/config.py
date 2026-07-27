from functools import lru_cache
from pathlib import Path

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
    jupyter_enabled: bool = False
    studio_storage_dir: str = str(
        Path(__file__).resolve().parents[1] / "storage" / "studio"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def studio_storage_path(self) -> Path:
        return Path(self.studio_storage_dir).resolve()

    def validate_production(self) -> list[str]:
        """生产环境安全校验——启动时调用。返回警告列表，空=通过。"""
        warnings = []
        if self.environment == "production":
            if self.secret_key == "change-me-in-production":
                warnings.append("DAI_SECRET_KEY 使用了默认值")
            if "change_me" in self.database_url or "dai_password" in self.database_url:
                warnings.append("DAI_DATABASE_URL 可能使用了默认密码")
            if "localhost" in self.redis_url and "redis" not in self.redis_url.split("@")[-1]:
                pass  # 容器环境 redis 主机名为 redis
            if self.cors_origins == "http://localhost:5173,http://127.0.0.1:5173" and \
               "localhost" not in (self.cors_origins or ""):
                warnings.append("DAI_CORS_ORIGINS 使用了开发默认值")
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
