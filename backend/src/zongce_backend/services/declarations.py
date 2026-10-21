"""能力分申报：增删改查、提交流程、证明材料、审核。"""

import hashlib
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..catalog import suggested_score
from ..config import Settings
from ..errors import AppError, ForbiddenError, NotFoundError
from ..models import (
    AcademicYear,
    Declaration,
    DeclarationStatus,
    EvidenceFile,
    ReviewAction,
    ReviewRecord,
    Role,
    User,
    YearStatus,
    utcnow,
)
from ..schemas.declarations import DeclarationCreate, DeclarationUpdate, ReviewRequest
from ..storage import FileStorage
from .rules import catalog_of
from .years import get_year, require_not_closed

_EDITABLE = (DeclarationStatus.DRAFT, DeclarationStatus.REJECTED)
# 按文件内容识别类型，不信任客户端声明的 Content-Type（CLAUDE.md §11）
_SIGNATURES = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
)


def _require_open(year: AcademicYear) -> None:
    if year.status != YearStatus.OPEN:
        raise AppError("该学年当前不在申报期")


def get_declaration(db: Session, declaration_id: int) -> Declaration:
    declaration = db.get(Declaration, declaration_id)
    if declaration is None:
        raise NotFoundError("申报不存在")
    return declaration


def can_view(user: User, d: Declaration) -> bool:
    return (
        d.student_id == user.id
        or user.has_role(Role.COLLEGE_ADMIN)
        or (
            user.has_role(Role.CLASS_REVIEWER)
            and user.class_name is not None
            and user.class_name == d.student.class_name
        )
    )


def _viewable(db: Session, user: User, declaration_id: int) -> Declaration:
    d = get_declaration(db, declaration_id)
    if not can_view(user, d):
        raise NotFoundError("申报不存在")
    return d


def _owned(db: Session, user: User, declaration_id: int) -> Declaration:
    d = _viewable(db, user, declaration_id)
    if d.student_id != user.id:
        raise ForbiddenError("只能修改自己的申报")
    return d


def _suggest(
    db: Session,
    year: AcademicYear,
    code: str,
    option_code: str | None,
    team_size: int | None,
    team_position: int | None,
    concurrent_rank: int | None,
    quantity: int | None,
) -> Decimal | None:
    catalog = catalog_of(year.rule_version)
    return suggested_score(
        catalog.item(code),
        option_code=option_code,
        team_size=team_size,
        team_position=team_position,
        concurrent_rank=concurrent_rank,
        quantity=quantity,
        coefficients=catalog.concurrent_coefficients,
    )


def create(db: Session, user: User, data: DeclarationCreate) -> Declaration:
    if not user.has_role(Role.STUDENT):
        raise ForbiddenError("只有学生账号可以申报")
    year = get_year(db, data.year_id)
    _require_open(year)
    suggested = _suggest(
        db, year, data.catalog_code, data.option_code, data.team_size, data.team_position,
        data.concurrent_rank, data.quantity,
    )  # fmt: skip
    d = Declaration(
        year_id=year.id,
        student_id=user.id,
        catalog_code=data.catalog_code,
        option_code=data.option_code,
        title=data.title,
        description=data.description,
        team_size=data.team_size,
        team_position=data.team_position,
        concurrent_rank=data.concurrent_rank,
        quantity=data.quantity,
        claimed_score=None if data.claimed_score is None else Decimal(data.claimed_score),
        suggested_score=suggested,
        status=DeclarationStatus.DRAFT,
    )
    db.add(d)
    db.commit()
    return d


def update(db: Session, user: User, declaration_id: int, data: DeclarationUpdate) -> Declaration:
    d = _owned(db, user, declaration_id)
    year = get_year(db, d.year_id)
    _require_open(year)
    if d.status not in _EDITABLE:
        raise AppError("只有草稿或被驳回的申报可以修改")
    fields = data.model_fields_set
    for name in fields:
        value = getattr(data, name)
        if name == "claimed_score":
            value = None if value is None else Decimal(value)
        setattr(d, name, value)
    d.suggested_score = _suggest(
        db, year, d.catalog_code, d.option_code, d.team_size, d.team_position,
        d.concurrent_rank, d.quantity,
    )  # fmt: skip
    d.status = DeclarationStatus.DRAFT
    db.commit()
    return d


def submit(db: Session, user: User, declaration_id: int) -> Declaration:
    d = _owned(db, user, declaration_id)
    _require_open(get_year(db, d.year_id))
    if d.status not in _EDITABLE:
        raise AppError("只有草稿或被驳回的申报可以提交")
    d.status = DeclarationStatus.SUBMITTED
    d.submitted_at = utcnow()
    db.commit()
    return d


def withdraw(db: Session, user: User, declaration_id: int) -> Declaration:
    d = _owned(db, user, declaration_id)
    _require_open(get_year(db, d.year_id))
    if d.status not in (*_EDITABLE, DeclarationStatus.SUBMITTED):
        raise AppError("已通过或已撤回的申报不能撤回")
    d.status = DeclarationStatus.WITHDRAWN
    db.commit()
    return d


def get_for(db: Session, user: User, declaration_id: int) -> Declaration:
    return _viewable(db, user, declaration_id)


def list_for(
    db: Session,
    user: User,
    *,
    mine: bool,
    year_id: int | None,
    status: DeclarationStatus | None,
    class_name: str | None,
) -> list[Declaration]:
    query = select(Declaration).join(Declaration.student).order_by(Declaration.id)
    if mine or not (user.has_role(Role.COLLEGE_ADMIN) or user.has_role(Role.CLASS_REVIEWER)):
        query = query.where(Declaration.student_id == user.id)
    elif not user.has_role(Role.COLLEGE_ADMIN):
        if user.class_name is None:
            return []
        query = query.where(User.class_name == user.class_name)
    elif class_name:
        query = query.where(User.class_name == class_name)
    if year_id is not None:
        query = query.where(Declaration.year_id == year_id)
    if status is not None:
        query = query.where(Declaration.status == status)
    return list(db.scalars(query).unique())


# ---------- 证明材料 ----------


def _sniff(data: bytes) -> tuple[str, str]:
    for signature, content_type, suffix in _SIGNATURES:
        if data.startswith(signature):
            return content_type, suffix
    raise AppError("只支持 PDF、PNG、JPEG 格式的证明材料")


def add_evidence(
    db: Session,
    user: User,
    declaration_id: int,
    filename: str,
    data: bytes,
    settings: Settings,
    storage: FileStorage,
) -> EvidenceFile:
    d = _owned(db, user, declaration_id)
    _require_open(get_year(db, d.year_id))
    if d.status not in _EDITABLE:
        raise AppError("只有草稿或被驳回的申报可以上传材料")
    if not data:
        raise AppError("文件为空")
    if len(data) > settings.max_upload_bytes:
        raise AppError(f"文件超过大小上限（{settings.max_upload_bytes // 1024 // 1024} MB）")
    if len(d.evidence) >= settings.max_files_per_declaration:
        raise AppError(f"每条申报最多上传 {settings.max_files_per_declaration} 个文件")
    content_type, suffix = _sniff(data)
    stored_name = storage.save(data, suffix)
    evidence = EvidenceFile(
        declaration_id=d.id,
        original_name=(filename or "未命名")[-255:],
        stored_name=stored_name,
        content_type=content_type,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by=user.id,
    )
    db.add(evidence)
    db.commit()
    db.refresh(d)
    return evidence


def _evidence(db: Session, evidence_id: int) -> EvidenceFile:
    evidence = db.get(EvidenceFile, evidence_id)
    if evidence is None:
        raise NotFoundError("材料不存在")
    return evidence


def read_evidence(
    db: Session, user: User, evidence_id: int, storage: FileStorage
) -> tuple[EvidenceFile, bytes]:
    evidence = _evidence(db, evidence_id)
    _viewable(db, user, evidence.declaration_id)
    return evidence, storage.load(evidence.stored_name)


def delete_evidence(db: Session, user: User, evidence_id: int, storage: FileStorage) -> None:
    evidence = _evidence(db, evidence_id)
    d = _owned(db, user, evidence.declaration_id)
    _require_open(get_year(db, d.year_id))
    if d.status not in _EDITABLE:
        raise AppError("只有草稿或被驳回的申报可以删除材料")
    stored_name = evidence.stored_name
    db.delete(evidence)
    db.commit()
    storage.delete(stored_name)


# ---------- 审核 ----------


def review(db: Session, reviewer: User, declaration_id: int, req: ReviewRequest) -> Declaration:
    d = _viewable(db, reviewer, declaration_id)
    year = get_year(db, d.year_id)
    require_not_closed(year)
    if d.student_id == reviewer.id:
        raise ForbiddenError("不能审核自己的申报")
    is_admin = reviewer.has_role(Role.COLLEGE_ADMIN)
    if not is_admin and not reviewer.has_role(Role.CLASS_REVIEWER):
        raise ForbiddenError("没有审核权限")
    if d.status == DeclarationStatus.APPROVED and not is_admin:
        raise ForbiddenError("已通过的申报只有学院管理员可以改分")
    if d.status not in (DeclarationStatus.SUBMITTED, DeclarationStatus.APPROVED):
        raise AppError("只能审核已提交或已通过的申报")

    after: Decimal | None
    if req.action == ReviewAction.REJECT:
        if req.score is not None:
            raise AppError("驳回时不需要填写分数")
        after, status = None, DeclarationStatus.REJECTED
    elif req.action == ReviewAction.APPROVE:
        if req.score is not None:
            raise AppError("直接通过时不填写分数；需要改分请选择“改分”")
        after = d.suggested_score if d.suggested_score is not None else d.claimed_score
        if after is None:
            raise AppError("该申报没有建议分或申报分，请选择“改分”并填写分数")
        status = DeclarationStatus.APPROVED
    else:
        if req.score is None:
            raise AppError("改分必须填写分数")
        after, status = Decimal(req.score), DeclarationStatus.APPROVED

    if after is not None:
        item = catalog_of(year.rule_version).item(d.catalog_code)
        low = None if item.min_score is None else Decimal(item.min_score)
        high = None if item.max_score is None else Decimal(item.max_score)
        if (low is not None and after < low) or (high is not None and after > high):
            raise AppError(f"“{item.name}”的分数应在 {item.min_score}–{item.max_score} 之间")

    before = d.approved_score
    d.approved_score, d.status = after, status
    d.reviewer_id, d.reviewed_at = reviewer.id, utcnow()
    db.add(
        ReviewRecord(
            declaration_id=d.id,
            reviewer_id=reviewer.id,
            action=req.action,
            score_before=before,
            score_after=after,
            reason=req.reason,
        )
    )
    audit.record(
        db, actor=reviewer, action=f"declaration.{req.action.value}", entity_type="declaration",
        entity_id=d.id, field="approved_score", before=before, after=after, reason=req.reason,
    )  # fmt: skip
    db.commit()
    return d


def reviews_of(db: Session, user: User, declaration_id: int) -> list[ReviewRecord]:
    _viewable(db, user, declaration_id)
    query = select(ReviewRecord).where(ReviewRecord.declaration_id == declaration_id)
    return list(db.scalars(query.order_by(ReviewRecord.id)))
