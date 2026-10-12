"""全部数据表（CLAUDE.md §8 M1）。分数一律用 DecimalText 精确存储。"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, DecimalText, TimestampMixin, enum_column, utcnow
from .enums import AppealStatus, DeclarationStatus, ReviewAction, Role, ScoreField, YearStatus


class User(TimestampMixin, Base):
    """账号。学生的 username 为学号；由学院管理员批量导入。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    class_name: Mapped[str | None] = mapped_column(String(64), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    role_rows: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def roles(self) -> frozenset[Role]:
        return frozenset(r.role for r in self.role_rows)

    def has_role(self, role: Role) -> bool:
        return role in self.roles


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[Role] = mapped_column(enum_column(Role), primary_key=True)

    user: Mapped[User] = relationship(back_populates="role_rows")


class RuleVersion(TimestampMixin, Base):
    """一个版本的计分规则（rules/*.json 的完整内容）。"""

    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    ability_catalog: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sha256: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class AcademicYear(TimestampMixin, Base):
    """学年（每学年评定一次，办法正文第十三条）。"""

    __tablename__ = "academic_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    rule_version_id: Mapped[int] = mapped_column(ForeignKey("rule_versions.id"))
    status: Mapped[YearStatus] = mapped_column(enum_column(YearStatus), default=YearStatus.DRAFT)

    rule_version: Mapped[RuleVersion] = relationship(lazy="joined")


class Declaration(TimestampMixin, Base):
    """能力分申报条目（细则附件 2 第二条）。"""

    __tablename__ = "declarations"

    id: Mapped[int] = mapped_column(primary_key=True)
    year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    catalog_code: Mapped[str] = mapped_column(String(64))
    option_code: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    team_size: Mapped[int | None] = mapped_column(Integer)
    team_position: Mapped[int | None] = mapped_column(Integer)
    concurrent_rank: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int | None] = mapped_column(Integer)
    claimed_score: Mapped[Decimal | None] = mapped_column(DecimalText())
    suggested_score: Mapped[Decimal | None] = mapped_column(DecimalText())
    approved_score: Mapped[Decimal | None] = mapped_column(DecimalText())
    status: Mapped[DeclarationStatus] = mapped_column(
        enum_column(DeclarationStatus), default=DeclarationStatus.DRAFT
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime())
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    student: Mapped[User] = relationship(foreign_keys=[student_id], lazy="joined")
    evidence: Mapped[list["EvidenceFile"]] = relationship(
        back_populates="declaration", lazy="selectin", order_by="EvidenceFile.id"
    )


class EvidenceFile(TimestampMixin, Base):
    """证明材料。按随机名存储，原文件名只用于展示。"""

    __tablename__ = "evidence_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    declaration_id: Mapped[int] = mapped_column(ForeignKey("declarations.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(64), unique=True)
    content_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    declaration: Mapped[Declaration] = relationship(back_populates="evidence")


class ReviewRecord(TimestampMixin, Base):
    """审核记录：通过 / 改分 / 驳回，理由必填。"""

    __tablename__ = "review_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    declaration_id: Mapped[int] = mapped_column(ForeignKey("declarations.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[ReviewAction] = mapped_column(enum_column(ReviewAction))
    score_before: Mapped[Decimal | None] = mapped_column(DecimalText())
    score_after: Mapped[Decimal | None] = mapped_column(DecimalText())
    reason: Mapped[str] = mapped_column(Text)


class ImportBatch(TimestampMixin, Base):
    """一次文件导入（账号或学院成绩表）。"""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    year_id: Mapped[int | None] = mapped_column(ForeignKey("academic_years.id"))
    kind: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class CollegeRecord(TimestampMixin, Base):
    """学院提供的计分输入（GPA、基础分四项、思想品德评议等），每人每项一条。

    思想品德子项可以是直接得分（value）或评议名单（ratings，十进制字符串数组）。
    """

    __tablename__ = "college_records"
    __table_args__ = (UniqueConstraint("year_id", "student_id", "field"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    field: Mapped[ScoreField] = mapped_column(enum_column(ScoreField))
    value: Mapped[Decimal | None] = mapped_column(DecimalText())
    ratings: Mapped[list[Any] | None] = mapped_column(JSON)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"))
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)


class ScoreResult(Base):
    """核算结果快照（每学年每人一条，重新核算时覆盖并写审计日志）。"""

    __tablename__ = "score_results"
    __table_args__ = (UniqueConstraint("year_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rule_version_id: Mapped[int] = mapped_column(ForeignKey("rule_versions.id"))
    final_score: Mapped[Decimal] = mapped_column(DecimalText())
    gpa: Mapped[Decimal] = mapped_column(DecimalText())
    quality_total: Mapped[Decimal] = mapped_column(DecimalText())
    moral_total: Mapped[Decimal | None] = mapped_column(DecimalText())
    competence_total: Mapped[Decimal | None] = mapped_column(DecimalText())
    ability_total: Mapped[Decimal] = mapped_column(DecimalText())
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    computed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    student: Mapped[User] = relationship(foreign_keys=[student_id], lazy="joined")


class Publication(TimestampMixin, Base):
    """班级公示（办法正文第十四条：班级线上公示 3 天）。snapshot 为公示时的排名快照。"""

    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(primary_key=True)
    year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    class_name: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime())
    ends_at: Mapped[datetime] = mapped_column(DateTime())
    snapshot: Mapped[list[Any]] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime())


class Appeal(TimestampMixin, Base):
    """公示期内的异议（办法正文第十六条）。"""

    __tablename__ = "appeals"

    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[AppealStatus] = mapped_column(
        enum_column(AppealStatus), default=AppealStatus.PENDING
    )
    response: Mapped[str | None] = mapped_column(Text)
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime())


class AuditLog(Base):
    """审计日志：谁、何时、改了什么、改前值、改后值、理由（CLAUDE.md §8 M1）。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    field: Mapped[str | None] = mapped_column(String(64))
    before: Mapped[str | None] = mapped_column(Text)
    after: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
