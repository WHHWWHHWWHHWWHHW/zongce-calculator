"""公示与异议。"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from ..models import Appeal, AppealStatus
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
    student_username: str
    student_name: str
    class_name: str | None
    content: str
    status: AppealStatus
    response: str | None
    handled_by: int | None
    handled_at: UtcDatetime | None
    created_at: UtcDatetime

    @classmethod
    def of(cls, appeal: Appeal) -> "AppealOut":
        return cls(
            id=appeal.id,
            publication_id=appeal.publication_id,
            student_id=appeal.student_id,
            student_username=appeal.student.username,
            student_name=appeal.student.name,
            class_name=appeal.student.class_name,
            content=appeal.content,
            status=appeal.status,
            response=appeal.response,
            handled_by=appeal.handled_by,
            handled_at=appeal.handled_at,
            created_at=appeal.created_at,
        )
