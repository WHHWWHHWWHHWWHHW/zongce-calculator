"""从 Excel / CSV 的行（已读成字符串二维表）中解析获奖名单类表单。"""

import re
from collections.abc import Sequence
from decimal import Decimal

from .models import ExtractedRecord, TableExtraction
from .normalize import compact, number, student_id
from .options import match_option

STUDENT_KEYS = ("学号",)
NAME_KEYS = ("姓名",)
OPTION_KEYS = ("类别", "级别", "等级", "奖项", "获奖", "名次", "荣誉", "称号", "职务", "结果")
VALUE_KEYS = ("分值", "加分", "得分")
STUDENT_ID = re.compile(r"[A-Z0-9_]{3,32}")
NORMALIZED_PENALTY = Decimal("0.05")


def _find(label: str, keys: tuple[str, ...]) -> bool:
    return any(k in compact(label) for k in keys)


def extract_award_rows(
    rows: Sequence[Sequence[str]],
    options: Sequence[tuple[str, str]],
    *,
    context: str = "",
) -> TableExtraction:
    """rows 第一行为表头。options 为该项目的 (选项编码, 选项名称)。

    context 是对整张表都成立的说明，例如“一类赛事”，与每行的等级原文拼在一起判断选项。
    """
    if not rows:
        return TableExtraction(records=(), columns={})
    header = [str(h) for h in rows[0]]
    columns: dict[str, str] = {}
    student_col = name_col = value_col = None
    option_cols: list[int] = []
    ignored: list[str] = []
    for col, label in enumerate(header):
        if student_col is None and _find(label, STUDENT_KEYS):
            student_col, columns[label] = col, "学号"
        elif name_col is None and _find(label, NAME_KEYS):
            name_col, columns[label] = col, "姓名"
        elif value_col is None and _find(label, VALUE_KEYS):
            value_col, columns[label] = col, "分值"
        elif _find(label, OPTION_KEYS):
            option_cols.append(col)
            columns[label] = "等级"
        elif label.strip():
            ignored.append(label)
    if student_col is None:
        raise ValueError("表头缺少“学号”列")

    records: list[ExtractedRecord] = []
    skipped: list[int] = []
    for number_, row in enumerate(rows[1:], start=2):

        def cell(col: int | None, row: Sequence[str] = row) -> str:
            return str(row[col]).strip() if col is not None and col < len(row) else ""

        raw_id = cell(student_col)
        if not raw_id:
            skipped.append(number_)
            continue
        sid, clean = student_id(raw_id)
        issues: list[str] = []
        option_text = " ".join(t for t in (context, *(cell(c) for c in option_cols)) if t)
        matched = match_option(option_text, options)
        confidence = matched.confidence
        if matched.option_code is None:
            issues.append(matched.reason)
        if not STUDENT_ID.fullmatch(sid):
            issues.insert(0, "学号格式不正确")
            confidence = Decimal(0)
        elif not clean:
            issues.insert(0, "学号含空格或全角字符，已规范化")
            confidence = max(Decimal(0), confidence - NORMALIZED_PENALTY)
        value = None
        if value_col is not None and cell(value_col):
            value, value_clean = number(cell(value_col))
            if value is None or not value_clean:
                issues.append("分值无法识别" if value is None else "分值单元格含其他文字")
        records.append(
            ExtractedRecord(
                row=number_,
                student_id=sid,
                name=cell(name_col) or None,
                option_text=option_text,
                option_code=matched.option_code,
                value=value,
                confidence=confidence,
                issues=tuple(issues),
            )
        )
    return TableExtraction(
        records=tuple(records),
        columns=columns,
        ignored_columns=tuple(ignored),
        skipped_rows=tuple(skipped),
    )
