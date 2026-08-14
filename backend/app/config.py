import re
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
    # ── Kernel 镜像（Phase 5） ────────────────────────────────
    # 已绑定环境版本的实验记录用环境 digest 启动；该配置仅用于未绑定环境版本的
    # 存量兼容路径与开发环境。安全参数不在此处放松。
    kernel_image: str = "dai-kernel-python:latest"
    jupyter_enabled: bool = False
    studio_storage_dir: str = str(
        Path(__file__).resolve().parents[1] / "storage" / "studio"
    )
    # 教师上传视频存储目录——生产必须挂载持久卷，不能依赖容器可写层
    video_storage_dir: str = str(
        Path(__file__).resolve().parents[1] / "storage" / "videos"
    )
    video_max_upload_bytes: int = Field(default=500 * 1024 * 1024, gt=0)
    video_playback_url_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    # 课程封面存储目录——生产必须挂载持久卷（cover_data），与视频目录同规则
    cover_storage_dir: str = str(
        Path(__file__).resolve().parents[1] / "storage" / "covers"
    )
    cover_max_upload_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    # 判题临时文件目录——Docker Compose 下必须与 judge 容器挂载相同路径
    judge_work_dir: str = ""
    # 宿主机侧判题工作目录——DoD 模式下传给 Docker daemon 的宿主机绝对路径
    # 未设置时回退到 judge_work_dir（适用于非 DoD / 开发环境）
    judge_host_work_dir: str = ""

    # ── AI 智能代码评分（DeepSeek） ──
    # TASK-020（F-21）：AI 数据治理上线门——审批完成前默认关闭。
    # 生产通过 DAI_AI_ENABLED=true 显式启用（compose 默认 -false）；关闭时零外呼、保留人工评分。
    ai_enabled: bool = False
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

        # 环境档位基础镜像——生产必须使用带 digest 的引用（供应链可复现，拒绝可变标签）
        if not re.fullmatch(
            r"[^\s@]+@sha256:[0-9a-f]{64}", self.env_base_image
        ):
            errors.append(
                "DAI_ENV_BASE_IMAGE 必须是带 @sha256: digest 的基础镜像引用"
                f"（当前: {self.env_base_image}），拒绝可变标签"
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

    @property
    def video_storage_path(self) -> Path:
        return Path(self.video_storage_dir).resolve()

    @property
    def cover_storage_path(self) -> Path:
        return Path(self.cover_storage_dir).resolve()

    # ── 登录限流 ──
    login_rate_limit_window_seconds: int = Field(default=900, ge=60)
    login_rate_limit_user_max_failures: int = Field(default=10, ge=1)
    login_rate_limit_ip_max_attempts: int = Field(default=30, ge=1)
    # 仅当部署在可信反向代理之后（生产 Nginx）才置 True；
    # 此时客户端 IP 取 X-Forwarded-For 最右一跳，否则使用直连地址。
    trusted_proxy: bool = False

    # ── 环境档位控制面（Phase 1） ──────────────────────────────
    env_build_queue_name: str = "environment:build:queue"
    env_build_timeout_seconds: int = Field(default=3600, ge=60, le=86400)
    env_image_repository: str = "dai-env"
    env_base_image: str = "python:3.12-slim"
    env_build_log_max_bytes: int = Field(default=60 * 1024, ge=1024, le=1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()
