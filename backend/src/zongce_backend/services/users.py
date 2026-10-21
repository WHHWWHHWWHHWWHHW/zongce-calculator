"""账号：登录、改密码、批量导入、重置密码、修改。"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import Settings
from ..errors import AppError, ConflictError, NotFoundError, UnauthorizedError
from ..models import Role, User, UserRole
from ..ratelimit import LoginLimiter
from ..schemas.users import CreatedAccount, PasswordReset, RowError, UserImportResult, UserUpdate
from ..security import create_access_token, generate_password, hash_password, verify_password
from ..tabular import read_table

_USERNAME = re.compile(r"[A-Za-z0-9_]{3,32}")
_ROLE_NAMES = {
    "学生": Role.STUDENT,
    "student": Role.STUDENT,
    "班级审核员": Role.CLASS_REVIEWER,
    "审核员": Role.CLASS_REVIEWER,
    "class_reviewer": Role.CLASS_REVIEWER,
    "学院管理员": Role.COLLEGE_ADMIN,
    "管理员": Role.COLLEGE_ADMIN,
    "college_admin": Role.COLLEGE_ADMIN,
}
_HEADERS = {
    "username": ("学号", "账号", "用户名"),
    "name": ("姓名",),
    "class_name": ("班级",),
    "roles": ("角色",),
}


def login(
    db: Session,
    username: str,
    password: str,
    settings: Settings,
    limiter: LoginLimiter,
    client_ip: str,
) -> tuple[User, str]:
    limiter.check(username, client_ip)
    user = db.scalar(select(User).where(User.username == username))
    ok = verify_password(None if user is None else user.password_hash, password)
    if user is None or not ok or not user.is_active:
        limiter.failed(username, client_ip)
        raise UnauthorizedError("账号或密码错误")
    limiter.succeeded(username)
    return user, create_access_token(user.id, user.token_version, settings)


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(user.password_hash, old_password):
        raise AppError("原密码不正确")
    if new_password == old_password:
        raise AppError("新密码不能与原密码相同")
    if new_password == user.username:
        raise AppError("密码不能与账号相同")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.token_version += 1
    audit.record(
        db, actor=user, action="user.password_changed", entity_type="user", entity_id=user.id
    )
    db.commit()


def set_roles(user: User, roles: set[Role]) -> None:
    current = {row.role: row for row in user.role_rows}
    for role, row in current.items():
        if role not in roles:
            user.role_rows.remove(row)
    for role in roles - set(current):
        user.role_rows.append(UserRole(role=role))


def _parse_roles(text: str) -> set[Role]:
    parts = [p for p in re.split(r"[,，、/;；\s]+", text.strip()) if p]
    if not parts:
        return {Role.STUDENT}
    roles = set()
    for part in parts:
        role = _ROLE_NAMES.get(part.lower() if part.isascii() else part)
        if role is None:
            raise ValueError(f"未知角色“{part}”")
        roles.add(role)
    return roles


def _header_index(header: list[str]) -> dict[str, int]:
    index: dict[str, int] = {}
    for col, label in enumerate(header):
        for key, names in _HEADERS.items():
            if key not in index and any(n in label for n in names):
                index[key] = col
    missing = [_HEADERS[k][0] for k in ("username", "name") if k not in index]
    if missing:
        raise AppError(f"表头缺少列：{'、'.join(missing)}")
    return index


def import_users(
    db: Session, actor: User, filename: str, data: bytes, settings: Settings
) -> UserImportResult:
    rows = read_table(filename, data)
    if not rows:
        raise AppError("表格为空")
    index = _header_index(rows[0])
    created: list[CreatedAccount] = []
    errors: list[RowError] = []
    updated = unchanged = 0
    seen: set[str] = set()

    def cell(row: list[str], key: str) -> str:
        col = index.get(key)
        return row[col].strip() if col is not None and col < len(row) else ""

    for number, row in enumerate(rows[1:], start=2):
        username, name = cell(row, "username"), cell(row, "name")
        class_name = cell(row, "class_name") or None
        if not _USERNAME.fullmatch(username):
            errors.append(RowError(row=number, message="账号应为 3–32 位字母、数字或下划线"))
            continue
        if username in seen:
            errors.append(RowError(row=number, message="账号在表格中重复"))
            continue
        seen.add(username)
        if not name or len(name) > 64 or (class_name is not None and len(class_name) > 64):
            errors.append(RowError(row=number, message="姓名不能为空，姓名和班级不超过 64 个字符"))
            continue
        try:
            roles = _parse_roles(cell(row, "roles"))
        except ValueError as exc:
            errors.append(RowError(row=number, message=str(exc)))
            continue
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            password = generate_password(settings.initial_password_length)
            user = User(
                username=username,
                name=name,
                class_name=class_name,
                password_hash=hash_password(password),
                must_change_password=True,
            )
            set_roles(user, roles)
            db.add(user)
            created.append(CreatedAccount(username=username, name=name, initial_password=password))
        elif (user.name, user.class_name, user.roles) != (name, class_name, frozenset(roles)):
            user.name, user.class_name = name, class_name
            set_roles(user, roles)
            updated += 1
        else:
            unchanged += 1
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="user.imported",
        entity_type="import",
        entity_id=filename[:64],
        after=f"新建 {len(created)}，更新 {updated}，未变 {unchanged}，错误 {len(errors)}",
    )
    db.commit()
    return UserImportResult(created=created, updated=updated, unchanged=unchanged, errors=errors)


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("账号不存在")
    return user


def reset_password(db: Session, actor: User, user_id: int, settings: Settings) -> PasswordReset:
    user = get_user(db, user_id)
    password = generate_password(settings.initial_password_length)
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.token_version += 1
    audit.record(
        db, actor=actor, action="user.password_reset", entity_type="user", entity_id=user.id
    )
    db.commit()
    return PasswordReset(username=user.username, initial_password=password)


def update_user(db: Session, actor: User, user_id: int, change: UserUpdate) -> User:
    user = get_user(db, user_id)
    if user.id == actor.id and (
        change.is_active is False
        or (change.roles is not None and Role.COLLEGE_ADMIN not in change.roles)
    ):
        raise ConflictError("不能停用自己或取消自己的管理员角色")
    before = f"{user.name}|{user.class_name}|{','.join(sorted(user.roles))}|{user.is_active}"
    if change.name is not None:
        user.name = change.name
    if change.class_name is not None:
        user.class_name = change.class_name or None
    if change.roles is not None:
        set_roles(user, set(change.roles))
    if change.is_active is not None:
        user.is_active = change.is_active
        user.token_version += 1
    db.flush()
    after = f"{user.name}|{user.class_name}|{','.join(sorted(user.roles))}|{user.is_active}"
    audit.record(
        db, actor=actor, action="user.updated", entity_type="user", entity_id=user.id,
        before=before, after=after,
    )  # fmt: skip
    db.commit()
    return user


def list_users(db: Session, class_name: str | None, role: Role | None) -> list[User]:
    query = select(User).order_by(User.class_name, User.username)
    if class_name:
        query = query.where(User.class_name == class_name)
    if role is not None:
        query = query.where(User.role_rows.any(UserRole.role == role))
    return list(db.scalars(query))
