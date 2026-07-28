from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
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
    # 宿主机侧判题工作目录——DoD 模式下传给 Docker daemon 的宿主机绝对路径
    # 未设置时回退到 judge_work_dir（适用于非 DoD / 开发环境）
    judge_host_work_dir: str = ""

    # ── AI 智能代码评分（DeepSeek） ──
    ai_enabled: bool = True
    ai_base_url: str = "https://aihub.codingpython.cn"
    ai_api_key: SecretStr = SecretStr("")
    ai_model: str = "deepseek-v4-flash"
    ai_timeout_seconds: float = Field(default=60.0, gt=0, le=180)
    ai_max_retries: int = Field(default=3, ge=0, le=8)
    ai_queue_name: str = "judge:ai:queue"

    @property
    def ai_ready(self) -> bool:
        """AI 评分是否就绪：启用且已配置 API Key"""
        return self.ai_enabled and bool(self.ai_api_key.get_secret_value().strip())

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
        if not origins:
            errors.append("DAI_CORS_ORIGINS 未设置，生产环境必须指定实际域名")
        # 拒绝任何 localhost/127.0.0.1 起源（生产不应使用开发地址）
        localhost_origins = [o for o in origins if "localhost" in o or "127.0.0.1" in o or "::1" in o]
        if localhost_origins:
            errors.append(f"DAI_CORS_ORIGINS 包含本地开发地址: {', '.join(localhost_origins)}，生产环境必须使用实际域名")
        if "*" in origins:
            errors.append("DAI_CORS_ORIGINS 不允许使用通配符 *")

        # Docker-outside-of-Docker 模式中，容器内目录不能直接交给宿主机
        # Docker daemon。配置了共享工作目录时，必须同时给出宿主机绝对路径。
        if self.judge_work_dir and not self.judge_host_work_dir:
            errors.append(
                "DAI_JUDGE_HOST_WORK_DIR 未设置，生产环境判题容器无法挂载宿主机工作目录"
            )

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
