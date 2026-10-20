"""把表单记录按学号与学生申报逐条匹配，并按置信度分流（CLAUDE.md §8 M4）。

分流结果只是建议：
- fast_track（可快速通过）：学号、姓名、项目、等级都与一条待审核申报一致，且置信度不低于阈值。
  仍需审核员批量确认后才会通过；
- manual（人工复核）：等级不符、学号不存在、姓名不符、置信度低等；
- info（仅提示）：名单上有但学生没有申报，或名单重复。
"""

from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .models import ExtractedRecord

DEFAULT_THRESHOLD = Decimal("0.9")


class MatchStatus(StrEnum):
    CONSISTENT = "consistent"  # 与申报一致
    OPTION_MISMATCH = "option_mismatch"  # 申报的等级与名单不同
    UNCERTAIN = "uncertain"  # 名单上的等级无法确定
    NOT_DECLARED = "not_declared"  # 名单上有，学生没有申报这一项目
    UNKNOWN_STUDENT = "unknown_student"  # 学号不存在或不是学生
    NAME_MISMATCH = "name_mismatch"  # 姓名与账号不一致
    DUPLICATE = "duplicate"  # 名单中重复


class Route(StrEnum):
    FAST_TRACK = "fast_track"
    MANUAL = "manual"
    INFO = "info"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StudentRef(_Model):
    student_id: str
    name: str
    class_name: str | None = None


class DeclarationRef(_Model):
    """待审核（已提交）的申报。"""

    id: int
    student_id: str
    option_code: str | None


class Suggestion(_Model):
    row: int
    student_id: str
    status: MatchStatus
    route: Route
    confidence: Decimal
    declaration_id: int | None = None
    form_option: str | None = None
    declared_option: str | None = None
    reasons: tuple[str, ...] = ()


class MatchReport(_Model):
    suggestions: tuple[Suggestion, ...]
    unmatched_declarations: tuple[int, ...]  # 已提交但名单中没有的申报，照常人工审核

    def count(self, route: Route) -> int:
        return sum(1 for s in self.suggestions if s.route is route)


def _same_name(form: str | None, account: str) -> bool:
    return form is None or form.replace(" ", "") == account.replace(" ", "")


def match(
    records: Sequence[ExtractedRecord],
    declarations: Sequence[DeclarationRef],
    students: Sequence[StudentRef],
    *,
    threshold: Decimal = DEFAULT_THRESHOLD,
) -> MatchReport:
    """declarations 只应包含同一学年、同一申报项目、状态为“已提交”的申报。"""
    accounts = {s.student_id: s for s in students}
    pending: dict[str, list[DeclarationRef]] = {}
    for d in declarations:
        pending.setdefault(d.student_id, []).append(d)
    used: set[int] = set()
    seen: set[tuple[str, str | None, str]] = set()
    suggestions: list[Suggestion] = []

    for record in records:

        def suggest(
            status: MatchStatus,
            route: Route,
            reasons: tuple[str, ...],
            declaration: DeclarationRef | None = None,
            record: ExtractedRecord = record,
        ) -> Suggestion:
            return Suggestion(
                row=record.row,
                student_id=record.student_id,
                status=status,
                route=route,
                confidence=record.confidence,
                declaration_id=None if declaration is None else declaration.id,
                form_option=record.option_code,
                declared_option=None if declaration is None else declaration.option_code,
                reasons=reasons,
            )

        key = (record.student_id, record.option_code, record.group)
        if key in seen:
            suggestions.append(suggest(MatchStatus.DUPLICATE, Route.INFO, ("名单中重复出现",)))
            continue
        seen.add(key)
        account = accounts.get(record.student_id)
        if account is None:
            reasons = record.issues if record.by_name else ("学号不存在或不是学生", *record.issues)
            suggestions.append(suggest(MatchStatus.UNKNOWN_STUDENT, Route.MANUAL, reasons))
            continue
        candidates = [d for d in pending.get(record.student_id, []) if d.id not in used]
        if not candidates:
            reasons = ("学生没有申报这一项目（或已审核）",)
            suggestions.append(suggest(MatchStatus.NOT_DECLARED, Route.INFO, reasons))
            continue
        same = next((d for d in candidates if d.option_code == record.option_code), None)
        declaration = same or candidates[0]
        notes = list(record.issues)
        if record.option_code is None and not record.unit_item:
            status = MatchStatus.UNCERTAIN
        elif same is None:
            status = MatchStatus.OPTION_MISMATCH
            notes.append("申报的等级与名单不同")
        elif not _same_name(record.name, account.name):
            status = MatchStatus.NAME_MISMATCH
            notes.append("姓名与账号不一致")
        else:
            status = MatchStatus.CONSISTENT
        if status is MatchStatus.CONSISTENT and record.confidence < threshold:
            notes.append(f"置信度 {record.confidence} 低于阈值 {threshold}")
        fast = status is MatchStatus.CONSISTENT and record.confidence >= threshold
        used.add(declaration.id)
        route = Route.FAST_TRACK if fast else Route.MANUAL
        suggestions.append(suggest(status, route, tuple(notes), declaration))

    unmatched = tuple(d.id for d in declarations if d.id not in used)
    return MatchReport(suggestions=tuple(suggestions), unmatched_declarations=unmatched)
