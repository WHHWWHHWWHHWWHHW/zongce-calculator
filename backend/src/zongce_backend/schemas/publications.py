"""公示与异议。"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from ..models import AppealStatus
from .common import ApiModel, Reason, UtcDatetime
from .scores import RankRow


class PublicationCreate(ApiModel):
    class_name: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    days: int | None = Field(
        default=None, ge=1, le=30, description="省略时用配置的默认天数（3 天）"
    )
    title: Annotated[str, StringConstraints(max_length=200)] | None = None


class PublicationOut(ApiModel):
    id: int
    year_id: int
    class_name: str
    title: str
    starts_at: UtcDatetime
    ends_at: UtcDatetime
    closed_at: UtcDatetime | None
    is_open: bool
    rows: list[RankRow]


class AppealCreate(ApiModel):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class AppealResolve(ApiModel):
    status: Literal[AppealStatus.ACCEPTED, AppealStatus.REJECTED]
    response: Reason


class AppealOut(ApiModel):
    id: int
    publication_id: int
    student_id: int
    content: str
    status: AppealStatus
    response: str | None
    handled_by: int | None
    handled_at: UtcDatetime | None
    created_at: UtcDatetime
