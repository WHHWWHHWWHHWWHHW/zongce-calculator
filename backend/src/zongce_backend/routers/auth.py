"""登录与账号自助。"""

from fastapi import APIRouter

from ..deps import AppSettings, AuthenticatedUser, DbSession
from ..schemas.common import Message
from ..schemas.users import ChangePasswordRequest, LoginRequest, TokenResponse, UserOut
from ..services import users as service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse, summary="登录（学号/账号 + 密码）")
def login(body: LoginRequest, db: DbSession, settings: AppSettings) -> TokenResponse:
    user, token = service.login(db, body.username, body.password, settings)
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
