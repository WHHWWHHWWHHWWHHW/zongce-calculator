"""AI 辅助审核（CLAUDE.md §8 M4）：学院名单与学生申报比对，给出“可快速通过 / 人工复核”的建议。

比对只读、不改分；“可快速通过”的条目必须由审核员批量确认，确认时逐条走正常的审核流程
（写审核记录与审计日志，CLAUDE.md §3 第 4 条）。
"""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from zongce_ai import (
    AiDisabledError,
    AiUnavailableError,
    DeclarationRef,
    MatchStatus,
    Route,
    StudentRef,
    extract_award_rows,
    image_extractor,
    match,
)

from ..config import Settings
from ..errors import AppError
from ..models import Declaration, DeclarationStatus, ReviewAction, Role, User, UserRole
from ..schemas.ai import (
    AiStatus,
    AwardMatchResult,
    FastTrackConfirm,
    FastTrackItem,
    FastTrackResult,
    MatchSuggestionOut,
)
from ..schemas.declarations import ReviewRequest
from ..tabular import read_table
from . import declarations as declaration_service
from .rules import catalog_of
from .years import get_year

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".pdf")


def status(settings: Settings) -> AiStatus:
    return AiStatus(
        provider=settings.ai_provider.value,
        table_matching=True,
        image_recognition=False,  # OCR 与大模型尚未接入（CLAUDE.md §13 第 4 项）
        fast_track_threshold=format(settings.ai_fast_track_threshold, "f"),
    )


def _visible_students(db: Session, user: User) -> list[User]:
    query = select(User).where(
        User.is_active.is_(True), User.role_rows.any(UserRole.role == Role.STUDENT)
    )
    if not user.has_role(Role.COLLEGE_ADMIN):
        if user.class_name is None:
            return []
        query = query.where(User.class_name == user.class_name)
    return list(db.scalars(query))


def award_match(
    db: Session,
    user: User,
    year_id: int,
    catalog_code: str,
    filename: str,
    data: bytes,
    context: str,
    settings: Settings,
) -> AwardMatchResult:
    year = get_year(db, year_id)
    item = catalog_of(year.rule_version).item(catalog_code)
    if not item.options:
        raise AppError(f"“{item.name}”没有固定的等级选项，无法按名单比对")
    if filename.lower().endswith(_IMAGE_SUFFIXES):
        try:
            image_extractor(settings.ai_provider).extract(data, filename)
        except (AiDisabledError, AiUnavailableError) as exc:
            raise AppError(str(exc)) from exc
        raise AppError("图片识别尚未接入")  # pragma: no cover - 接入 OCR 后改为解析结果
    options = [(o.code, o.name) for o in item.options]
    try:
        extraction = extract_award_rows(read_table(filename, data), options, context=context)
    except ValueError as exc:
        raise AppError(str(exc)) from exc

    students = _visible_students(db, user)
    by_username = {s.username: s for s in students}
    pending = list(
        db.scalars(
            select(Declaration).where(
                Declaration.year_id == year.id,
                Declaration.catalog_code == catalog_code,
                Declaration.status == DeclarationStatus.SUBMITTED,
                Declaration.student_id.in_([s.id for s in students]),
            )
        )
    )
    by_id = {d.id: d for d in pending}
    report = match(
        extraction.records,
        [
            DeclarationRef(id=d.id, student_id=d.student.username, option_code=d.option_code)
            for d in pending
        ],
        [StudentRef(student_id=s.username, name=s.name) for s in students],
        threshold=settings.ai_fast_track_threshold,
    )

    hidden: set[str] = set()
    if not user.has_role(Role.COLLEGE_ADMIN):  # 其他班的学生对班级审核员不可见，不逐条显示
        unknown = [
            s.student_id for s in report.suggestions if s.status is MatchStatus.UNKNOWN_STUDENT
        ]
        hidden = set(db.scalars(select(User.username).where(User.username.in_(unknown))))
    option_names = dict(options)
    rows: list[MatchSuggestionOut] = []
    for s in report.suggestions:
        if s.student_id in hidden:
            continue
        account = by_username.get(s.student_id)
        declaration = by_id.get(s.declaration_id) if s.declaration_id is not None else None
        rows.append(
            MatchSuggestionOut(
                row=s.row,
                student_username=s.student_id,
                student_name=None if account is None else account.name,
                status=s.status,
                route=s.route,
                confidence=format(s.confidence, "f"),
                declaration_id=s.declaration_id,
                declaration_title=None if declaration is None else declaration.title,
                form_option=s.form_option,
                form_option_name=option_names.get(s.form_option or ""),
                declared_option=s.declared_option,
                declared_option_name=option_names.get(s.declared_option or ""),
                reasons=list(s.reasons),
            )
        )
    counts = Counter(r.route.value for r in rows)
    return AwardMatchResult(
        catalog_code=item.code,
        catalog_name=item.name,
        columns=extraction.columns,
        ignored_columns=list(extraction.ignored_columns),
        skipped_rows=list(extraction.skipped_rows),
        out_of_scope_rows=len(report.suggestions) - len(rows),
        suggestions=rows,
        unmatched_declaration_ids=list(report.unmatched_declarations),
        counts={route.value: counts[route.value] for route in Route},
    )


def confirm_fast_track(
    db: Session, user: User, year_id: int, body: FastTrackConfirm
) -> FastTrackResult:
    """审核员批量确认“可快速通过”的申报：逐条按“通过”审核，写审核记录与审计日志。"""
    get_year(db, year_id)
    reason = f"与学院名单一致（{body.source}），经 AI 辅助比对后由审核员批量确认"
    items: list[FastTrackItem] = []
    for declaration_id in dict.fromkeys(body.declaration_ids):
        try:
            d = declaration_service.get_declaration(db, declaration_id)
            if d.year_id != year_id:
                raise AppError("申报不属于该学年")
            if d.status != DeclarationStatus.SUBMITTED:
                raise AppError("只能确认待审核的申报")
            declaration_service.review(
                db, user, declaration_id, ReviewRequest(action=ReviewAction.APPROVE, reason=reason)
            )
        except AppError as exc:
            db.rollback()
            items.append(
                FastTrackItem(declaration_id=declaration_id, ok=False, message=exc.message)
            )
        else:
            items.append(FastTrackItem(declaration_id=declaration_id, ok=True, message="已通过"))
    return FastTrackResult(approved=sum(i.ok for i in items), items=items)
