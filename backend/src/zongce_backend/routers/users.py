"""账号管理（学院管理员）。"""

from fastapi import APIRouter, UploadFile

from ..deps import AdminUser, AppSettings, DbSession
from ..errors import AppError
from ..models import Role
from ..schemas.users import PasswordReset, UserImportResult, UserOut, UserUpdate
from ..services import users as service

router = APIRouter(prefix="/users", tags=["账号管理"])


def read_upload(file: UploadFile, limit: int) -> bytes:
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise AppError(f"文件超过大小上限（{limit // 1024 // 1024} MB）")
    return data


@router.post(
    "/import",
    response_model=UserImportResult,
    summary="批量导入账号",
    description="上传 .xlsx/.csv，表头需含“学号”“姓名”，可选“班级”“角色”。"
    "新账号的随机初始密码只在本次响应中返回一次。",
)
def import_users(
    file: UploadFile, admin: AdminUser, db: DbSession, settings: AppSettings
) -> UserImportResult:
    data = read_upload(file, settings.max_upload_bytes)
    return service.import_users(db, admin, file.filename or "users.xlsx", data, settings)


@router.get("", response_model=list[UserOut], summary="账号列表")
def list_users(
    _: AdminUser, db: DbSession, class_name: str | None = None, role: Role | None = None
) -> list[UserOut]:
    return [UserOut.of(u) for u in service.list_users(db, class_name, role)]


@router.patch(
    "/{user_id}", response_model=UserOut, summary="修改账号（姓名、班级、角色、启用状态）"
)
def update_user(user_id: int, body: UserUpdate, admin: AdminUser, db: DbSession) -> UserOut:
    return UserOut.of(service.update_user(db, admin, user_id, body))


@router.post(
    "/{user_id}/reset-password", response_model=PasswordReset, summary="重置为随机初始密码"
)
def reset_password(
    user_id: int, admin: AdminUser, db: DbSession, settings: AppSettings
) -> PasswordReset:
    return service.reset_password(db, admin, user_id, settings)
