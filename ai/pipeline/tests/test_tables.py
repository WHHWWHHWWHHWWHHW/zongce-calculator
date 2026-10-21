"""获奖名单表格 → 表单记录。"""

from decimal import Decimal

import pytest

from ai_helpers import options
from zongce_ai import extract_award_rows

COMPETITION = options("competition")


def test_extract_rows_with_context_and_issues() -> None:
    rows = [
        ["序号", "学号", "姓名", "竞赛名称", "获奖级别", "获奖等级", "加分", ""],
        ["1", "TEST01002", "测试学生1-02", "某学科竞赛", "省级", "一等奖", "20"],
        ["2", "ＴＥＳＴ０１００３ ", "测试学生1-03", "某学科竞赛", "省级", "二等奖", "15分"],
        ["3", "", "测试学生1-04", "某学科竞赛", "省级", "三等奖", ""],
        ["4", "TEST-1", "测试学生1-05", "某学科竞赛", "国家级", "一等奖", "约 40"],
        ["5", "TEST01006", "", "某学科竞赛", "省级", "优胜", "1，2"],
        ["6", "TEST01007", "测试学生1-07", "某学科竞赛", "校级", "三等奖"],
    ]
    result = extract_award_rows(rows, COMPETITION, context="一类赛事")
    assert result.columns == {
        "学号": "学号", "姓名": "姓名", "获奖级别": "等级", "获奖等级": "等级", "加分": "分值",
    }  # fmt: skip
    assert result.ignored_columns == ("序号", "竞赛名称")
    assert result.skipped_rows == (4,)
    first, second, bad_id, unknown, no_value = result.records
    assert (first.row, first.student_id, first.option_code) == (2, "TEST01002", "c1_provincial_1")
    assert (first.value, first.confidence, first.issues) == (Decimal(20), Decimal("0.95"), ())
    assert first.option_text == "一类赛事 省级 一等奖"
    assert second.student_id == "TEST01003"
    assert second.confidence == Decimal("0.90")
    assert second.issues == ("学号含空格或全角字符，已规范化", "分值单元格含其他文字")
    assert (bad_id.confidence, bad_id.issues[0]) == (Decimal(0), "学号格式不正确")
    assert bad_id.value == Decimal(40)
    assert (unknown.name, unknown.option_code, unknown.value) == (None, None, None)
    assert unknown.issues == ("原文缺少区分信息（如赛事类别、级别或奖项）", "分值无法识别")
    assert unknown.confidence == Decimal("0.4")
    assert (no_value.option_code, no_value.value) == ("c1_university_3", None)


def test_requires_student_column() -> None:
    with pytest.raises(ValueError, match="学号"):
        extract_award_rows([["姓名", "等级"]], COMPETITION)


def test_empty_table() -> None:
    assert extract_award_rows([], COMPETITION).records == ()
