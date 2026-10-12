"""班级排名与 Excel 导出。"""

import io
from collections import defaultdict
from decimal import Decimal

from openpyxl import Workbook

from zongce_engine import format_score

from ..models import AcademicYear, ScoreResult
from ..schemas.scores import RankRow


def _fmt(value: Decimal | None) -> str | None:
    return None if value is None else format_score(value)


def rank(results: list[ScoreResult]) -> list[RankRow]:
    """按班级分组，组内按综测成绩从高到低排名；同分名次相同（如 1、2、2、4）。"""
    by_class: dict[str | None, list[ScoreResult]] = defaultdict(list)
    for result in results:
        by_class[result.student.class_name].append(result)
    rows: list[RankRow] = []
    for class_name in sorted(by_class, key=lambda c: c or ""):
        ordered = sorted(by_class[class_name], key=lambda r: (-r.final_score, r.student.username))
        previous: Decimal | None = None
        current_rank = 0
        for position, result in enumerate(ordered, start=1):
            if result.final_score != previous:
                current_rank, previous = position, result.final_score
            rows.append(
                RankRow(
                    rank=current_rank,
                    class_name=class_name,
                    username=result.student.username,
                    name=result.student.name,
                    final_score=format_score(result.final_score),
                    gpa=format_score(result.gpa),
                    quality_total=format_score(result.quality_total),
                    moral_total=_fmt(result.moral_total),
                    competence_total=_fmt(result.competence_total),
                    ability_total=format_score(result.ability_total),
                )
            )
    return rows


_COLUMNS = (
    ("班级", "class_name"),
    ("排名", "rank"),
    ("学号", "username"),
    ("姓名", "name"),
    ("学业水平评价成绩（GPA）", "gpa"),
    ("思想品德行为习惯", "moral_total"),
    ("综合能力表现", "competence_total"),
    ("其中能力分", "ability_total"),
    ("综合素质评价成绩", "quality_total"),
    ("综合测评成绩", "final_score"),
)
_NUMERIC = {
    "gpa",
    "moral_total",
    "competence_total",
    "ability_total",
    "quality_total",
    "final_score",
}


def export_xlsx(year: AcademicYear, rows: list[RankRow]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = f"{year.name} 综测排名"
    sheet.append([title for title, _ in _COLUMNS])
    for row in rows:
        data = row.model_dump()
        values: list[object] = []
        for _, key in _COLUMNS:
            value = data[key]
            values.append(Decimal(value) if key in _NUMERIC and value is not None else value)
        sheet.append(values)
    for index, column in enumerate(sheet.iter_cols(min_row=2)):
        if _COLUMNS[index][1] in _NUMERIC:
            for cell in column:
                cell.number_format = "0.0000"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
