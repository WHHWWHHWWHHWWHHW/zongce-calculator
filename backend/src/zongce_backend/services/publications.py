"""公示（快照 + 期限）与异议。"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import Settings
from ..errors import AppError, ForbiddenError, NotFoundError
from ..models import Appeal, AppealStatus, Publication, Role, ScoreResult, User, utcnow
from ..schemas.publications import AppealResolve, PublicationCreate, PublicationOut
from ..schemas.scores import RankRow
from .ranking import rank
from .years import get_year, require_not_closed


def is_open(publication: Publication) -> bool:
    now = utcnow()
    return publication.closed_at is None and publication.starts_at <= now < publication.ends_at


def to_out(publication: Publication) -> PublicationOut:
    return PublicationOut(
        id=publication.id,
        year_id=publication.year_id,
        class_name=publication.class_name,
        title=publication.title,
        starts_at=publication.starts_at,
        ends_at=publication.ends_at,
        closed_at=publication.closed_at,
        is_open=is_open(publication),
        rows=[RankRow.model_validate(r) for r in publication.snapshot],
    )


def create(
    db: Session, actor: User, year_id: int, data: PublicationCreate, settings: Settings
) -> Publication:
    year = get_year(db, year_id)
    require_not_closed(year)
    results = [
        r
        for r in db.scalars(select(ScoreResult).where(ScoreResult.year_id == year.id)).unique()
        if r.student.class_name == data.class_name
    ]
    if not results:
        raise AppError("该班级还没有核算结果，请先核算")
    rows = rank(results)
    now = utcnow()
    publication = Publication(
        year_id=year.id,
        class_name=data.class_name,
        title=data.title or f"{year.name} 学年 {data.class_name} 综合测评成绩公示",
        starts_at=now,
        ends_at=now + timedelta(days=data.days or settings.publication_days),
        snapshot=[r.model_dump(mode="json") for r in rows],
        created_by=actor.id,
    )
    db.add(publication)
    db.flush()
    audit.record(
        db, actor=actor, action="publication.created", entity_type="publication",
        entity_id=publication.id, after=f"{data.class_name} {len(rows)} 人",
    )  # fmt: skip
    db.commit()
    return publication


def _visible(user: User, publication: Publication) -> bool:
    return user.has_role(Role.COLLEGE_ADMIN) or (
        user.class_name is not None and user.class_name == publication.class_name
    )


def get(db: Session, user: User, publication_id: int) -> Publication:
    publication = db.get(Publication, publication_id)
    if publication is None or not _visible(user, publication):
        raise NotFoundError("公示不存在")
    return publication


def list_for(db: Session, user: User, year_id: int | None) -> list[Publication]:
    query = select(Publication).order_by(Publication.id.desc())
    if year_id is not None:
        query = query.where(Publication.year_id == year_id)
    if not user.has_role(Role.COLLEGE_ADMIN):
        if user.class_name is None:
            return []
        query = query.where(Publication.class_name == user.class_name)
    return list(db.scalars(query))


def close(db: Session, actor: User, publication_id: int) -> Publication:
    publication = get(db, actor, publication_id)
    if publication.closed_at is None:
        publication.closed_at = utcnow()
        audit.record(
            db, actor=actor, action="publication.closed", entity_type="publication",
            entity_id=publication.id,
        )  # fmt: skip
        db.commit()
    return publication


def create_appeal(db: Session, user: User, publication_id: int, content: str) -> Appeal:
    publication = get(db, user, publication_id)
    if not user.has_role(Role.STUDENT) or user.class_name != publication.class_name:
        raise ForbiddenError("只有本班学生可以对公示提出异议")
    if not is_open(publication):
        raise AppError("公示期已结束，不能再提出异议")
    appeal = Appeal(publication_id=publication.id, student_id=user.id, content=content)
    db.add(appeal)
    db.flush()
    audit.record(db, actor=user, action="appeal.created", entity_type="appeal", entity_id=appeal.id)
    db.commit()
    return appeal


def list_appeals(db: Session, user: User, publication_id: int | None) -> list[Appeal]:
    query = select(Appeal).order_by(Appeal.id)
    if publication_id is not None:
        query = query.where(Appeal.publication_id == publication_id)
    if not user.has_role(Role.COLLEGE_ADMIN):
        query = query.where(Appeal.student_id == user.id)
    return list(db.scalars(query))


def resolve_appeal(db: Session, actor: User, appeal_id: int, data: AppealResolve) -> Appeal:
    appeal = db.get(Appeal, appeal_id)
    if appeal is None:
        raise NotFoundError("异议不存在")
    if appeal.status != AppealStatus.PENDING:
        raise AppError("该异议已处理")
    appeal.status = data.status
    appeal.response = data.response
    appeal.handled_by, appeal.handled_at = actor.id, utcnow()
    audit.record(
        db, actor=actor, action="appeal.resolved", entity_type="appeal", entity_id=appeal.id,
        field="status", before=AppealStatus.PENDING.value, after=data.status.value,
        reason=data.response,
    )  # fmt: skip
    db.commit()
    return appeal
