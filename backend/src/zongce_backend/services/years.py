"""学年：创建、状态流转。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..errors import AppError, ConflictError, NotFoundError
from ..models import AcademicYear, User, YearStatus
from .rules import get_rule_version

# 允许的状态流转：未开放 → 申报中 ⇄ 审核中 → 已结束
_TRANSITIONS = {
    YearStatus.DRAFT: {YearStatus.OPEN},
    YearStatus.OPEN: {YearStatus.REVIEWING},
    YearStatus.REVIEWING: {YearStatus.OPEN, YearStatus.CLOSED},
    YearStatus.CLOSED: set(),
}


def create_year(db: Session, actor: User, name: str, rule_version_id: int) -> AcademicYear:
    get_rule_version(db, rule_version_id)
    if db.scalar(select(AcademicYear).where(AcademicYear.name == name)) is not None:
        raise ConflictError(f"学年 {name} 已存在")
    year = AcademicYear(name=name, rule_version_id=rule_version_id, status=YearStatus.DRAFT)
    db.add(year)
    db.flush()
    audit.record(
        db, actor=actor, action="year.created", entity_type="academic_year", entity_id=year.id,
        after=f"{name} rule_version={rule_version_id}",
    )  # fmt: skip
    db.commit()
    return year


def get_year(db: Session, year_id: int) -> AcademicYear:
    year = db.get(AcademicYear, year_id)
    if year is None:
        raise NotFoundError("学年不存在")
    return year


def list_years(db: Session) -> list[AcademicYear]:
    return list(db.scalars(select(AcademicYear).order_by(AcademicYear.name.desc())))


def set_status(db: Session, actor: User, year_id: int, status: YearStatus) -> AcademicYear:
    year = get_year(db, year_id)
    if status not in _TRANSITIONS[year.status]:
        raise AppError(f"学年状态不能从 {year.status.value} 变为 {status.value}")
    audit.record(
        db, actor=actor, action="year.status_changed", entity_type="academic_year",
        entity_id=year.id, field="status", before=year.status.value, after=status.value,
    )  # fmt: skip
    year.status = status
    db.commit()
    return year


def require_not_closed(year: AcademicYear) -> None:
    if year.status == YearStatus.CLOSED:
        raise AppError("该学年已结束，不能再修改")
