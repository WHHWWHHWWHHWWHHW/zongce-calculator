"""把活动名单条目变成可与申报匹配的表单记录：按“班级 + 姓名”找学生，按分值与等级定选项。

真实名单没有学号（ADR 0007），所以先在账号中找人：
- 班级和姓名都对上且唯一 → 采用；
- 只有姓名唯一（名单没写班级，或班级写法不同）→ 采用，但降低置信度，交人工确认；
- 重名或找不到 → 不猜，记录原因，转人工。
"""

from collections.abc import Sequence
from decimal import Decimal

from .activity_lists import ActivityEntry, choose_item
from .matching import StudentRef
from .models import ExtractedRecord
from .names import normalize_class

NAME_ONLY_CAP = Decimal("0.85")  # 只按姓名找到的，置信度不超过它（低于快速通过阈值）
# 同一专业在不同表中的写法
MAJOR_ALIASES = {"人工智能": "智能"}


def class_key(code: str | None) -> str | None:
    if code is None:
        return None
    normalized = normalize_class(code) or code.strip()
    for long, short in MAJOR_ALIASES.items():
        if normalized.startswith(long):
            return short + normalized[len(long) :]
    return normalized


def resolve(entry: ActivityEntry, students: Sequence[StudentRef]) -> tuple[StudentRef | None, str]:
    """返回 (学生, 说明)；找不到或重名时学生为 None。"""
    same_name = [s for s in students if s.name.replace(" ", "") == entry.name]
    if entry.class_code is not None:
        wanted = class_key(entry.class_code)
        same_class = [s for s in same_name if class_key(s.class_name) == wanted]
        if len(same_class) == 1:
            return same_class[0], ""
    if len(same_name) == 1:
        note = "名单未写班级，只按姓名找到" if entry.class_code is None else "班级与账号不一致"
        return same_name[0], note
    if same_name:
        return None, f"重名（{len(same_name)} 人），无法确定是哪位学生"
    return None, "按班级和姓名找不到学生"


def records_from_entries(
    entries: Sequence[ActivityEntry],
    item: tuple[str, Sequence[tuple[str, str, str]], str | None],
    students: Sequence[StudentRef],
    *,
    default_level: str = "院级",
) -> list[ExtractedRecord]:
    """item：(项目编码, [(选项编码, 选项名称, 分值)], 按次计分时的每次分值)。"""
    unit_item = item[2] is not None
    records = []
    for entry in entries:
        student, note = resolve(entry, students)
        choice = choose_item(entry, [item], default_level=default_level)
        issues = [note] if note else []
        if choice is None:
            issues.append("名单没有写分值或分值与该项目不符")
            confidence = Decimal(0)
            option = None
        else:
            confidence, option = choice.confidence, choice.option_code
            if option is None and not unit_item:
                issues.append(choice.reason)
        if student is not None and note:
            confidence = min(confidence, NAME_ONLY_CAP)
        label = f"{entry.class_code or ''} {entry.name}".strip()
        records.append(
            ExtractedRecord(
                row=entry.line,
                student_id=student.student_id if student is not None else label,
                name=entry.name,
                option_text=" ".join(
                    t
                    for t in (entry.level, f"{entry.points}分" if entry.points else "", entry.note)
                    if t
                ),
                option_code=option,
                value=entry.points,
                confidence=confidence,
                issues=tuple(issues),
                group=entry.activity,
                unit_item=unit_item and choice is not None,
                by_name=True,
            )
        )
    return records
