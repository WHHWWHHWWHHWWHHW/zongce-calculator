"""AI 辅助审核（CLAUDE.md §8 M4）：学院名单与学生申报比对，给出“可快速通过 / 人工复核”的建议。

比对只读、不改分；“可快速通过”的条目必须由审核员批量确认，确认时逐条走正常的审核流程
（写审核记录与审计日志，CLAUDE.md §3 第 4 条）。
"""

import io
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from zongce_ai import (
    AiDisabledError,
    AiUnavailableError,
    DeclarationRef,
    Route,
    StudentRef,
    extract_award_rows,
    image_extractor,
    match,
)
from zongce_ai.activity_lists import parse_activity_list
from zongce_ai.activity_records import class_key, records_from_entries
from zongce_ai.names import majors_from, normalize_class

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

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
_TEXT_SUFFIXES = (".pdf", ".txt")


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


def _active_students(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User).where(
                User.is_active.is_(True), User.role_rows.any(UserRole.role == Role.STUDENT)
            )
        )
    )


def _text_of(filename: str, data: bytes, settings: Settings) -> str:
    """名单文字：.txt 直接解码；.pdf 取文字层，没有文字层（扫描件）时需要 OCR。"""
    if filename.lower().endswith(".txt"):
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise AppError(
            "无法识别文本文件编码，请另存为 UTF-8"
        )  # pragma: no cover - gb18030 几乎都能解码
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:  # pdfplumber 对损坏文件抛出多种异常
        raise AppError("无法读取 PDF 文件") from exc
    if not text.strip():
        try:
            image_extractor(settings.ai_provider).extract(data, filename)
        except (AiDisabledError, AiUnavailableError) as exc:
            raise AppError(f"PDF 没有文字层（可能是扫描件）。{exc}") from exc
        raise AppError("图片识别尚未接入")  # pragma: no cover - 接入 OCR 后改为解析结果
    return text


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
    """上传学院名单并与待审核申报比对。

    - Excel / CSV：表格名单，按学号匹配（需要有“学号”列）；
    - PDF（带文字层）/ TXT：各部门的活动获奖名单，按“班级 + 姓名”找学生，按分值定选项（ADR 0007）。
    """
    year = get_year(db, year_id)
    item = catalog_of(year.rule_version).item(catalog_code)
    lower = filename.lower()
    if lower.endswith(_IMAGE_SUFFIXES):
        try:
            image_extractor(settings.ai_provider).extract(data, filename)
        except (AiDisabledError, AiUnavailableError) as exc:
            raise AppError(str(exc)) from exc
        raise AppError("图片识别尚未接入")  # pragma: no cover - 接入 OCR 后改为解析结果
    visible = _visible_students(db, user)
    options = [(o.code, o.name) for o in item.options]
    columns: dict[str, str] = {}
    ignored: list[str] = []
    skipped: list[int] = []
    if lower.endswith(_TEXT_SUFFIXES):
        if not item.options and item.unit_score is None:
            raise AppError(f"“{item.name}”需要人工给分，无法按名单比对")
        everyone = _active_students(db)
        refs = [StudentRef(student_id=s.username, name=s.name, class_name=s.class_name)
                for s in everyone]  # fmt: skip
        majors = majors_from(s.class_name for s in everyone if s.class_name)
        entries = parse_activity_list(_text_of(filename, data, settings), majors).entries
        if not entries:
            raise AppError("没有识别出名单：应包含“活动名称”、等级与分值，以及“班级 姓名”")
        scored = [(o.code, o.name, o.score) for o in item.options]
        records = records_from_entries(
            entries, (item.code, scored, item.unit_score), refs,
            default_level=context.strip() or "院级",
        )  # fmt: skip
        resolvable = everyone
    else:
        if not item.options:
            raise AppError(f"“{item.name}”没有固定的等级选项，无法按名单比对")
        try:
            extraction = extract_award_rows(read_table(filename, data), options, context=context)
        except ValueError as exc:
            raise AppError(str(exc)) from exc
        records = list(extraction.records)
        columns, ignored = extraction.columns, list(extraction.ignored_columns)
        skipped = list(extraction.skipped_rows)
        resolvable = visible

    students = visible
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
        records,
        [
            DeclarationRef(id=d.id, student_id=d.student.username, option_code=d.option_code)
            for d in pending
        ],
        [StudentRef(student_id=s.username, name=s.name) for s in resolvable],
        threshold=settings.ai_fast_track_threshold,
    )

    hidden: set[str] = set()
    if not user.has_role(Role.COLLEGE_ADMIN):  # 其他班的学生对班级审核员不可见，不逐条显示
        listed = [s.student_id for s in report.suggestions]
        known = set(db.scalars(select(User.username).where(User.username.in_(listed))))
        hidden = known - set(by_username)
        own = class_key(user.class_name)
        for s in report.suggestions:  # 按姓名没找到的：名单写的班级不是本班，也不显示
            code = normalize_class(s.student_id.split(" ")[0]) if " " in s.student_id else None
            if code is not None and class_key(code) != own:
                hidden.add(s.student_id)
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
        columns=columns,
        ignored_columns=ignored,
        skipped_rows=skipped,
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
