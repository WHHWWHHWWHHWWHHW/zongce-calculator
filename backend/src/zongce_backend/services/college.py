"""学院成绩表导入与单项修改（每次分值变化都写审计日志）。"""

import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from zongce_ai.activity_records import class_key
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
from ..tabular import read_sheets
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
    # 到梦空间学分汇总的“积分总和”即第二课堂积分；志愿章汇总的“总章数”即公益劳动次数
    # （负责人 2026-10-21 确定，CLAUDE.md §13 第 8 项）
    ScoreField.SECOND_CLASSROOM: ("第二课堂", "积分总和"),
    ScoreField.PUBLIC_SERVICE: ("公益劳动", "公益", "总章数"),
    ScoreField.FITNESS_TEST: ("体质健康", "体测", "体育测试"),
    ScoreField.DORM_CHECK: ("宿舍",),
    ScoreField.QUALITY_DIRECT: ("综合素质评价总分", "综合素质评价成绩", "综合素质总分"),
    ScoreField.POLITICAL: ("政治素养", "政治"),
    ScoreField.MORALITY: ("品德修养",),
    ScoreField.DISCIPLINE: ("纪律观念", "纪律"),
    ScoreField.INTEGRITY: ("诚信评价", "诚信"),
}
STUDENT_COLUMN = "学号"
CLASS_COLUMN = "班级"
NAME_COLUMN = "姓名"


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


@dataclass
class _Sheet:
    """一个工作表的列：按学号找学生；没有学号列时按“班级 + 姓名”找。"""

    student: int | None
    class_col: int | None
    name_col: int | None
    columns: dict[int, ScoreField] = dc_field(default_factory=dict)
    ignored: list[str] = dc_field(default_factory=list)


def _sheet_columns(header: list[str]) -> _Sheet:
    def find(word: str) -> int | None:
        return next((i for i, h in enumerate(header) if word in h), None)

    sheet = _Sheet(find(STUDENT_COLUMN), find(CLASS_COLUMN), find(NAME_COLUMN))
    if sheet.student is None and (sheet.class_col is None or sheet.name_col is None):
        raise AppError("表头缺少“学号”列（没有学号时，需要“班级”和“姓名”两列）")
    identity = {sheet.student, sheet.class_col, sheet.name_col}
    for col, label in enumerate(header):
        if col in identity or not label:
            continue
        score_field = match_field(label)
        if score_field is None or score_field in sheet.columns.values():
            sheet.ignored.append(label)
        else:
            sheet.columns[col] = score_field
    return sheet


class _Students:
    """导入时找学生：按学号，或按“班级 + 姓名”（志愿章汇总等没有学号的表）。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._by_class_name: dict[tuple[str | None, str], list[User]] | None = None

    def by_username(self, username: str) -> tuple[User | None, str]:
        student = self.db.scalar(select(User).where(User.username == username))
        if student is None or not student.has_role(Role.STUDENT):
            return None, f"学号 {username or '（空）'} 不存在或不是学生"
        return student, ""

    def by_class_name(self, class_name: str, name: str) -> tuple[User | None, str]:
        if self._by_class_name is None:
            index: dict[tuple[str | None, str], list[User]] = {}
            for user in self.db.scalars(select(User).where(User.is_active.is_(True))):
                if user.has_role(Role.STUDENT):
                    key = (class_key(user.class_name), user.name.replace(" ", ""))
                    index.setdefault(key, []).append(user)
            self._by_class_name = index
        found = self._by_class_name.get((class_key(class_name), name.replace(" ", "")), [])
        if len(found) == 1:
            return found[0], ""
        if found:
            return None, f"{class_name} 有 {len(found)} 名同名学生 {name}，请改用学号"
        return None, f"按班级和姓名找不到学生：{class_name or '（空班级）'} {name or '（空姓名）'}"


def import_table(
    db: Session, actor: User, year_id: int, filename: str, data: bytes
) -> CollegeImportResult:
    """导入学院成绩表。Excel 的每个工作表分别识别表头（如按年级分表的志愿章汇总）。"""
    year = get_year(db, year_id)
    require_not_closed(year)
    tables = [(name, rows) for name, rows in read_sheets(filename, data) if rows]
    if not tables:
        raise AppError("表格为空")
    errors: list[dict[str, str | int]] = []
    plans: list[tuple[str, list[list[str]], _Sheet]] = []
    for index, (name, rows) in enumerate(tables):
        try:
            plans.append((name, rows, _sheet_columns(rows[0])))
        except AppError as exc:
            if index == 0:
                raise
            errors.append({"row": 1, "message": f"[{name}] {exc.message}，已跳过该工作表"})
    if not any(plan.columns for _, _, plan in plans):
        raise AppError("没有识别出任何成绩列，请检查表头")

    batch = ImportBatch(
        year_id=year.id, kind="college_data", filename=filename[-255:], created_by=actor.id
    )
    db.add(batch)
    db.flush()
    reason = f"导入 {filename[-100:]}（批次 #{batch.id}）"
    students = _Students(db)
    several = len(tables) > 1
    changed = unchanged = 0
    mapped: dict[str, str] = {}
    ignored: list[str] = []
    for sheet_name, rows, plan in plans:
        prefix = f"[{sheet_name}] " if several else ""
        header = rows[0]
        mapped.update({header[c]: f.value for c, f in plan.columns.items()})
        ignored += [label for label in plan.ignored if label not in ignored]

        def cell(row: list[str], col: int | None) -> str:
            return row[col].strip() if col is not None and col < len(row) else ""

        for number, row in enumerate(rows[1:], start=2):
            if plan.student is not None:
                student, problem = students.by_username(cell(row, plan.student))
            else:
                student, problem = students.by_class_name(
                    cell(row, plan.class_col), cell(row, plan.name_col)
                )
            if student is None:
                errors.append({"row": number, "message": prefix + problem})
                continue
            for col, score_field in plan.columns.items():
                text = cell(row, col)
                if not text:
                    continue
                numbers = extract_numbers(text)
                if not numbers:
                    errors.append(
                        {"row": number, "message": f"{prefix}“{header[col]}”无法识别数值"}
                    )
                    continue
                if score_field in MORAL_SCORE_FIELDS and len(numbers) >= 2:
                    value, ratings = None, [format(n, "f") for n in numbers]
                else:
                    value, ratings = numbers[0], None
                if _upsert(db, actor, year, student, score_field, value, ratings, reason, batch.id):
                    changed += 1
                else:
                    unchanged += 1
    total_rows = sum(len(rows) - 1 for _, rows in tables)
    batch.row_count = total_rows
    db.commit()
    return CollegeImportResult(
        batch_id=batch.id,
        rows=total_rows,
        changed=changed,
        unchanged=unchanged,
        mapped_columns=mapped,
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
