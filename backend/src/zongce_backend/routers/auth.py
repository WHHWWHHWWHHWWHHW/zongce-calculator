"""登录与账号自助。"""

from fastapi import APIRouter, Request

from ..deps import AppSettings, AuthenticatedUser, DbSession
from ..schemas.common import Message
from ..schemas.users import ChangePasswordRequest, LoginRequest, TokenResponse, UserOut
from ..services import users as service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="登录（学号/账号 + 密码）",
    description=(
        "同一账号或同一 IP 在时间窗内登录失败次数过多时返回 429"
        "（响应头 Retry-After 给出等待秒数）。"
    ),
)
def login(
    body: LoginRequest, request: Request, db: DbSession, settings: AppSettings
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    user, token = service.login(
        db, body.username, body.password, settings, request.app.state.login_limiter, client_ip
    )
    return TokenResponse(
        access_token=token, must_change_password=user.must_change_password, user=UserOut.of(user)
    )


@router.post("/change-password", response_model=Message, summary="修改密码（首次登录必须先修改）")
def change_password(body: ChangePasswordRequest, user: AuthenticatedUser, db: DbSession) -> Message:
    service.change_password(db, user, body.old_password, body.new_password)
    return Message(message="密码已修改，请重新登录")


@router.get("/me", response_model=UserOut, summary="当前用户")
def me(user: AuthenticatedUser) -> UserOut:
    return UserOut.of(user)
