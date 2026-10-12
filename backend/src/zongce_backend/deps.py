"""FastAPI 依赖：配置、数据库会话、当前用户与角色校验。"""

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import Settings
from .errors import ForbiddenError, PasswordChangeRequiredError, UnauthorizedError
from .models import Role, User
from .security import decode_access_token
from .storage import FileStorage


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_storage(request: Request) -> FileStorage:
    storage: FileStorage = request.app.state.storage
    return storage


def get_db(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Storage = Annotated[FileStorage, Depends(get_storage)]
_bearer = HTTPBearer(auto_error=False, description="登录接口返回的 access_token")


def get_authenticated_user(
    db: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """已登录用户（允许尚未修改初始密码）。"""
    if credentials is None:
        raise UnauthorizedError("请先登录")
    user_id, version = decode_access_token(credentials.credentials, settings)
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.token_version != version:
        raise UnauthorizedError("登录已失效，请重新登录")
    return user


AuthenticatedUser = Annotated[User, Depends(get_authenticated_user)]


def get_current_user(user: AuthenticatedUser) -> User:
    """已登录且已修改初始密码的用户。"""
    if user.must_change_password:
        raise PasswordChangeRequiredError("首次登录请先修改初始密码")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = frozenset(roles)

    def checker(user: CurrentUser) -> User:
        if not user.roles & allowed:
            raise ForbiddenError("没有权限执行此操作")
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(Role.COLLEGE_ADMIN))]
ReviewerUser = Annotated[User, Depends(require_roles(Role.CLASS_REVIEWER, Role.COLLEGE_ADMIN))]
