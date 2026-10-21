"""运行配置：从环境变量（前缀 ZONGCE_）或当前目录的 .env 读取。示例见 deploy/.env.example。"""

from decimal import Decimal
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from zongce_ai import AiProvider


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ZONGCE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/zongce.sqlite3"
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=480, ge=5, le=7 * 24 * 60)
    upload_dir: Path = Path("./uploads")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    max_files_per_declaration: int = Field(default=10, ge=1)
    initial_password_length: int = Field(default=10, ge=8, le=64)
    publication_days: int = Field(default=3, ge=1, le=30)
    login_max_failures: int = Field(
        default=5, ge=1, description="同一账号在时间窗内允许的登录失败次数"
    )
    login_ip_max_failures: int = Field(
        default=20, ge=1, description="同一 IP 在时间窗内允许的失败次数"
    )
    login_window_minutes: int = Field(default=15, ge=1, le=24 * 60)
    cors_origins: list[str] = []
    frontend_dist: Path | None = Field(
        default=None,
        description="前端构建产物目录（frontend/dist）。设置后由后端同时提供页面，"
        "一个端口即可使用（本机演示，见 scripts/local-demo.sh）",
    )
    ai_provider: AiProvider = Field(
        default=AiProvider.NONE,
        description="CLAUDE.md 中的 AI_PROVIDER：none（默认，只解析表格）| local | remote",
    )
    ai_fast_track_threshold: Decimal = Field(
        default=Decimal("0.9"), ge=0, le=1, description="置信度不低于此值且与申报一致才建议快速通过"
    )
