"""FastAPI 应用。本机启动：uv run zongce serve（见 docs/本机运行.md）。"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .db import make_engine, make_session_factory
from .errors import install_error_handlers
from .ratelimit import LoginLimiter
from .routers import ai, audit, auth, declarations, publications, scores, users, years
from .storage import LocalFileStorage

API_PREFIX = "/api/v1"
VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]  # 取自环境变量 / .env
    engine = make_engine(settings.database_url)
    app = FastAPI(
        title="综测智能核算平台 API",
        version=VERSION,
        description="济南大学校创项目“基于 AI 辅助审核的综合测评智能核算平台”后端。"
        "分数一律以十进制字符串传输；计分由 zongce_engine 完成。",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.storage = LocalFileStorage(settings.upload_dir)
    app.state.login_limiter = LoginLimiter(
        max_per_user=settings.login_max_failures,
        max_per_ip=settings.login_ip_max_failures,
        window_seconds=settings.login_window_minutes * 60,
    )
    install_error_handlers(app)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    api = APIRouter(prefix=API_PREFIX)
    for module in (auth, users, years, declarations, scores, publications, audit, ai):
        api.include_router(module.router)

    @api.get("/health", tags=["系统"], summary="健康检查")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": VERSION}

    app.include_router(api)
    return app
