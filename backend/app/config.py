from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
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
    secret_key: str = Field(default="change-me-in-production", min_length=1)
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
    # 判题临时文件目录——Docker Compose 下必须与 judge 容器挂载相同路径
    judge_work_dir: str = ""

    @model_validator(mode="after")
    def _validate_production(self):
        """生产环境安全校验——不通过直接抛异常阻止启动"""
        if self.environment != "production":
            return self

        errors = []
        # 密钥校验
        if not self.secret_key or self.secret_key == "change-me-in-production":
            errors.append("DAI_SECRET_KEY 未设置或使用了默认值，生产环境必须设置唯一密钥")
        elif len(self.secret_key) < 16:
            errors.append("DAI_SECRET_KEY 长度不足（至少 16 字符）")

        # 数据库密码校验
        if "dai_password" in self.database_url or "change_me" in self.database_url:
            errors.append("DAI_DATABASE_URL 使用了默认密码，生产环境必须使用唯一密码")

        # CORS 校验
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        dev_defaults = {"http://localhost:5173", "http://127.0.0.1:5173"}
        if set(origins) == dev_defaults:
            errors.append("DAI_CORS_ORIGINS 使用了开发默认值，生产环境必须设置实际域名")
        if "*" in origins:
            errors.append("DAI_CORS_ORIGINS 不允许使用通配符 *")

        if errors:
            raise ValueError("生产环境配置校验失败:\n  - " + "\n  - ".join(errors))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def studio_storage_path(self) -> Path:
        return Path(self.studio_storage_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
