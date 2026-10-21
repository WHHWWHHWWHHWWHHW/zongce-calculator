"""学院成绩表导入与单项修改（每次分值变化都写审计日志）。"""

import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from zongce_engine import extract_numbers

from .. import audit
from ..errors import AppError, NotFoundError
from ..models import (
    MORAL_SCORE_FIELDS,
    AcademicYear,
    CollegeRecord,
    ImportBatch,
    Role,
    ScoreField,
    User,
)
from ..schemas.scores import CollegeImportResult, CollegeRecordUpdate
from ..tabular import read_table
from .years import get_year, require_not_closed

# 表头关键词沿用 legacy importFieldDefs（CLAUDE.md §2.1），按最长匹配识别
FIELD_KEYWORDS: dict[ScoreField, tuple[str, ...]] = {
    ScoreField.GPA: (
        "学分绩点",
        "平均学分绩点",
        "绩点",
        "GPA",
        "学业水平评价",
        "学业水平",
        "学业成绩",
    ),
    ScoreField.SECOND_CLASSROOM: ("第二课堂",),
    ScoreField.PUBLIC_SERVICE: ("公益劳动", "公益"),
    ScoreField.FITNESS_TEST: ("体质健康", "体测", "体育测试"),
    ScoreField.DORM_CHECK: ("宿舍",),
    ScoreField.QUALITY_DIRECT: ("综合素质评价总分", "综合素质评价成绩", "综合素质总分"),
    ScoreField.POLITICAL: ("政治素养", "政治"),
    ScoreField.MORALITY: ("品德修养",),
    ScoreField.DISCIPLINE: ("纪律观念", "纪律"),
    ScoreField.INTEGRITY: ("诚信评价", "诚信"),
}
STUDENT_COLUMN = "学号"


def normalize_label(label: str) -> str:
    """与 legacy normalizeLabel 相同：去掉括号内容、冒号和空白。"""
    return re.sub(r"[:：\s]", "", re.sub(r"[（(].*?[)）]", "", label))


def match_field(label: str) -> ScoreField | None:
    norm = normalize_label(label)
    best: ScoreField | None = None
    best_len = 0
    for field, keywords in FIELD_KEYWORDS.items():
        for keyword in keywords:
            if keyword in norm and len(keyword) > best_len:
                best, best_len = field, len(keyword)
    return best


def _describe(value: Decimal | None, ratings: list[str] | None) -> str | None:
    if ratings is not None:
        return "评议名单:" + ",".join(ratings)
    return None if value is None else format(value, "f")


def _upsert(
    db: Session,
    actor: User,
    year: AcademicYear,
    student: User,
    field: ScoreField,
    value: Decimal | None,
    ratings: list[str] | None,
    reason: str,
    batch_id: int | None,
) -> bool:
    """写入一项；值有变化时记审计日志并返回 True。"""
    record = db.scalar(
        select(CollegeRecord).where(
            CollegeRecord.year_id == year.id,
            CollegeRecord.student_id == student.id,
            CollegeRecord.field == field,
        )
    )
    before = None if record is None else _describe(record.value, record.ratings)
    after = _describe(value, ratings)
    if before == after:
        return False
    if record is None:
        record = CollegeRecord(year_id=year.id, student_id=student.id, field=field)
        db.add(record)
    record.value, record.ratings = value, ratings
    record.batch_id, record.updated_by = batch_id, actor.id
    audit.record(
        db, actor=actor, action="college_record.changed", entity_type="student",
        entity_id=student.id, field=f"{year.name}.{field.value}", before=before, after=after,
        reason=reason,
    )  # fmt: skip
    return True


def import_table(
    db: Session, actor: User, year_id: int, filename: str, data: bytes
) -> CollegeImportResult:
    year = get_year(db, year_id)
    require_not_closed(year)
    rows = read_table(filename, data)
    if not rows:
        raise AppError("表格为空")
    header = rows[0]
    student_col = next((i for i, h in enumerate(header) if STUDENT_COLUMN in h), None)
    if student_col is None:
        raise AppError("表头缺少“学号”列")
    columns: dict[int, ScoreField] = {}
    ignored: list[str] = []
    for col, label in enumerate(header):
        if col == student_col or not label:
            continue
        field = match_field(label)
        if field is None or field in columns.values():
            ignored.append(label)
        else:
            columns[col] = field
    if not columns:
        raise AppError("没有识别出任何成绩列，请检查表头")

    batch = ImportBatch(
        year_id=year.id, kind="college_data", filename=filename[-255:], created_by=actor.id
    )
    db.add(batch)
    db.flush()
    reason = f"导入 {filename[-100:]}（批次 #{batch.id}）"
    errors: list[dict[str, str | int]] = []
    changed = unchanged = 0
    for number, row in enumerate(rows[1:], start=2):
        username = row[student_col].strip() if student_col < len(row) else ""
        student = db.scalar(select(User).where(User.username == username))
        if student is None or not student.has_role(Role.STUDENT):
            errors.append(
                {"row": number, "message": f"学号 {username or '（空）'} 不存在或不是学生"}
            )
            continue
        for col, field in columns.items():
            text = row[col].strip() if col < len(row) else ""
            if not text:
                continue
            numbers = extract_numbers(text)
            if not numbers:
                errors.append({"row": number, "message": f"“{header[col]}”无法识别数值"})
                continue
            if field in MORAL_SCORE_FIELDS and len(numbers) >= 2:
                value, ratings = None, [format(n, "f") for n in numbers]
            else:
                value, ratings = numbers[0], None
            if _upsert(db, actor, year, student, field, value, ratings, reason, batch.id):
                changed += 1
            else:
                unchanged += 1
    batch.row_count = len(rows) - 1
    db.commit()
    return CollegeImportResult(
        batch_id=batch.id,
        rows=len(rows) - 1,
        changed=changed,
        unchanged=unchanged,
        mapped_columns={header[c]: f.value for c, f in columns.items()},
        ignored_columns=ignored,
        errors=errors,
    )


def update_record(
    db: Session, actor: User, year_id: int, username: str, field: ScoreField,
    change: CollegeRecordUpdate,
) -> CollegeRecord:  # fmt: skip
    year = get_year(db, year_id)
    require_not_closed(year)
    student = db.scalar(select(User).where(User.username == username))
    if student is None:
        raise NotFoundError("学生不存在")
    if change.ratings is not None and field not in MORAL_SCORE_FIELDS:
        raise AppError("只有思想品德四项可以录入评议名单")
    value = None if change.value is None else Decimal(change.value)
    _upsert(db, actor, year, student, field, value, change.ratings, change.reason, None)
    db.commit()
    record = db.scalar(
        select(CollegeRecord).where(
            CollegeRecord.year_id == year.id,
            CollegeRecord.student_id == student.id,
            CollegeRecord.field == field,
        )
    )
    assert record is not None
    return record


def list_records(
    db: Session, user: User, year_id: int, username: str | None
) -> list[tuple[CollegeRecord, str]]:
    get_year(db, year_id)
    query = (
        select(CollegeRecord, User.username)
        .join(User, User.id == CollegeRecord.student_id)
        .where(CollegeRecord.year_id == year_id)
        .order_by(User.username, CollegeRecord.field)
    )
    if not user.has_role(Role.COLLEGE_ADMIN):
        if user.has_role(Role.CLASS_REVIEWER) and user.class_name is not None:
            query = query.where(User.class_name == user.class_name)
        else:
            query = query.where(User.id == user.id)
    if username:
        query = query.where(User.username == username)
    return [(row[0], row[1]) for row in db.execute(query).all()]
