"""账号与认证。"""

from typing import Annotated

from pydantic import Field, StringConstraints

from ..models import Role, User
from .common import ApiModel

Username = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_]{3,32}$")]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserOut(ApiModel):
    id: int
    username: str
    name: str
    class_name: str | None
    roles: list[Role]
    must_change_password: bool
    is_active: bool

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            username=user.username,
            name=user.name,
            class_name=user.class_name,
            roles=sorted(user.roles),
            must_change_password=user.must_change_password,
            is_active=user.is_active,
        )


class LoginRequest(ApiModel):
    username: str = Field(max_length=32)
    password: str = Field(max_length=128)


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool
    user: UserOut


class ChangePasswordRequest(ApiModel):
    old_password: str = Field(max_length=128)
    new_password: Password


class CreatedAccount(ApiModel):
    username: str
    name: str
    initial_password: str


class RowError(ApiModel):
    row: int
    message: str


class UserImportResult(ApiModel):
    created: list[CreatedAccount]
    updated: int
    unchanged: int
    errors: list[RowError]


class UserUpdate(ApiModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None = None
    class_name: Annotated[str, StringConstraints(max_length=64)] | None = None
    roles: list[Role] | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class PasswordReset(ApiModel):
    username: str
    initial_password: str
