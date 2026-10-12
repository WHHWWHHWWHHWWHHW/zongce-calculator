"""业务枚举。值即数据库与 API 中的取值。"""

from enum import StrEnum


class Role(StrEnum):
    STUDENT = "student"
    CLASS_REVIEWER = "class_reviewer"
    COLLEGE_ADMIN = "college_admin"


class YearStatus(StrEnum):
    DRAFT = "draft"  # 未开放
    OPEN = "open"  # 申报中
    REVIEWING = "reviewing"  # 审核中（停止申报）
    CLOSED = "closed"  # 已结束


class DeclarationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ReviewAction(StrEnum):
    APPROVE = "approve"  # 按建议分 / 申报分通过
    ADJUST = "adjust"  # 改分后通过
    REJECT = "reject"  # 驳回


class ScoreField(StrEnum):
    """学院成绩表中的计分输入项（字段名与 CLAUDE.md §4 一致）。"""

    GPA = "gpa"
    QUALITY_DIRECT = "quality_direct"
    POLITICAL = "political"
    MORALITY = "morality"
    DISCIPLINE = "discipline"
    INTEGRITY = "integrity"
    SECOND_CLASSROOM = "second_classroom"
    PUBLIC_SERVICE = "public_service"
    FITNESS_TEST = "fitness_test"
    DORM_CHECK = "dorm_check"


MORAL_SCORE_FIELDS = frozenset(
    {ScoreField.POLITICAL, ScoreField.MORALITY, ScoreField.DISCIPLINE, ScoreField.INTEGRITY}
)


class AppealStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
