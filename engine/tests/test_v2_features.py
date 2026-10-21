"""规则 v2 准备的引擎能力：第二课堂阶梯计分加分数线（R-004）、思想品德附减分（R-001）。

v1 规则文件不使用这些能力，结果不变；这里在 v1 的基础上改出测试用规则。
"""

import copy
from decimal import Decimal as D
from typing import Any

import jsonschema
import pytest

from zongce_engine import PeerRatings, RuleError, RuleSet, ScoreInput, calculate
from zongce_engine.rules import StepCappedRule

SECOND = {
    "type": "step_capped",
    "id": "basic.second_classroom",
    "field": "second_classroom",
    "name": "第二课堂成绩单",
    "step": "0.5",
    "points_per_step": "0.25",
    "cap": "5",
    "min_value": "2",
    "source": "测试：附件 2 第一条阶梯读法，分数线为假设值",
}
DEDUCTION = {
    "id": "moral.deduction",
    "name": "附减分",
    "max": "20",
    "floor_fields": ["morality", "discipline", "integrity"],
    "source": "测试：附件 1 第五、六条",
}


_KEEP: dict[str, Any] = {}


def _v2(
    data: dict[str, Any], second: dict[str, Any] | None = None, deduction: Any = _KEEP
) -> dict[str, Any]:
    result = copy.deepcopy(data)
    result["competence"]["basic"][0] = {**SECOND, **(second or {})}
    deduction = DEDUCTION if deduction is _KEEP else deduction
    if deduction is not None:
        result["moral"]["deduction"] = deduction
    return result


@pytest.fixture
def v2(rules_data: dict[str, Any]) -> RuleSet:
    return RuleSet.from_dict(_v2(rules_data))


def test_v2_rules_parse_and_match_schema(
    rules_data: dict[str, Any], schema_data: dict[str, Any]
) -> None:
    data = _v2(rules_data)
    jsonschema.Draft202012Validator(schema_data).validate(data)
    rules = RuleSet.from_dict(data)
    second = rules.competence.basic[0]
    assert isinstance(second, StepCappedRule)
    assert (second.step, second.points_per_step, second.min_value) == (D("0.5"), D("0.25"), D(2))
    assert rules.moral.deduction is not None
    assert rules.moral.deduction.floor_fields == ("morality", "discipline", "integrity")
    assert "moral.deduction" in [r.id for r in rules.all_rules()]
    # 分数线与上限都可以不写
    plain = _v2(
        rules_data,
        second={"min_value": None},
        deduction={**DEDUCTION, "max": None, "floor_fields": []},
    )
    jsonschema.validate(plain, schema_data)
    parsed = RuleSet.from_dict(plain)
    assert parsed.competence.basic[0].min_value == 0  # type: ignore[union-attr]
    assert parsed.moral.deduction is not None
    assert parsed.moral.deduction.max is None
    del plain["competence"]["basic"][0]["min_value"]
    assert RuleSet.from_dict(plain).competence.basic[0].min_value == 0  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"second": {"step": "0"}}, r"basic\[0\]\.step: 必须大于 0"),
        ({"second": {"min_value": 2}}, r"basic\[0\]\.min_value"),
        ({"deduction": {**DEDUCTION, "max": "-1"}}, r"deduction\.max: 不能为负数"),
        ({"deduction": {**DEDUCTION, "max": 20}}, r"deduction\.max"),
        ({"deduction": {**DEDUCTION, "floor_fields": "morality"}}, "应为数组"),
        ({"deduction": {**DEDUCTION, "floor_fields": ["politics"]}}, "不是思想品德子项"),
        ({"deduction": {**DEDUCTION, "floor_fields": ["morality", "morality"]}}, "重复"),
        ({"deduction": {**DEDUCTION, "id": "moral"}}, "重复的规则 id"),
        ({"deduction": []}, r"moral\.deduction: 应为对象"),
    ],
)
def test_invalid_v2_rules(
    rules_data: dict[str, Any], changes: dict[str, Any], message: str
) -> None:
    with pytest.raises(RuleError, match=message):
        RuleSet.from_dict(_v2(rules_data, **changes))


@pytest.mark.parametrize(
    ("points", "expected", "raw", "capped"),
    [
        (None, "0", "0", False),
        ("1.5", "0", "0", False),  # 未达到分数线 2：全部不计
        ("-3", "0", "0", False),
        ("2", "1", "1", False),  # 达到分数线后全部积分都计：2 ÷ 0.5 × 0.25
        ("2.7", "1.25", "1.25", False),  # 阶梯：不足 0.5 的部分不计
        ("10", "5", "5", False),
        ("12.5", "5", "6.25", True),
    ],
)
def test_second_classroom_step_with_threshold(
    v2: RuleSet, points: str | None, expected: str, raw: str, capped: bool
) -> None:
    value = None if points is None else D(points)
    item = calculate(ScoreInput(second_classroom=value), v2).item("basic.second_classroom")
    assert (item.score, item.raw, item.capped) == (D(expected), D(raw), capped)


def _moral_input(deduction: str | None, morality: str = "8") -> ScoreInput:
    return ScoreInput(
        political=D("9"),
        morality=D(morality),
        discipline=D("4"),
        integrity=PeerRatings((D("4"), D("5"), D("4"))),
        moral_deduction=None if deduction is None else D(deduction),
    )


@pytest.mark.parametrize(
    ("deduction", "morality", "applied", "moral_total", "capped"),
    [
        (None, "8", "0", "25.3333333333", False),
        ("0", "8", "0", "25.3333333333", False),
        ("2.5", "8", "2.5", "22.8333333333", False),  # 院级通报批评一次
        ("17", "8", "16.3333333333", "9.0000000000", True),  # 三项只有 16.33…，最多扣到 0
        ("25", "10", "18.3333333333", "9.0000000000", True),
    ],
)
def test_moral_deduction(
    v2: RuleSet,
    deduction: str | None,
    morality: str,
    applied: str,
    moral_total: str,
    capped: bool,
) -> None:
    result = calculate(_moral_input(deduction, morality), v2)
    item = result.item("moral.deduction")
    q = D("1e-10")
    assert (-item.score).quantize(q) == D(applied)
    assert item.capped is capped
    assert result.moral_total is not None
    assert result.moral_total.quantize(q) == D(moral_total)


def test_deduction_max_only_and_unlimited(rules_data: dict[str, Any]) -> None:
    only_max = RuleSet.from_dict(_v2(rules_data, deduction={**DEDUCTION, "floor_fields": []}))
    result = calculate(_moral_input("25"), only_max)
    assert result.item("moral.deduction").score == D(-20)  # 上限 20 分
    assert result.moral_total is not None
    assert result.moral_total.quantize(D("1e-10")) == D("5.3333333333")  # 25.33… − 20
    unlimited = RuleSet.from_dict(
        _v2(rules_data, deduction={**DEDUCTION, "max": None, "floor_fields": []})
    )
    result = calculate(_moral_input("30"), unlimited)
    assert result.item("moral.deduction").score == D(-30)
    assert result.moral_total == D(0)
    assert result.item("moral").floored


def test_deduction_ignored_without_rule(rules: RuleSet, rules_data: dict[str, Any]) -> None:
    # v1 没有附减分规则：输入了减分也不影响结果，也没有减分明细
    with_input = calculate(_moral_input("5"), rules)
    without = calculate(_moral_input(None), rules)
    assert with_input.final_score == without.final_score
    with pytest.raises(KeyError):
        with_input.item("moral.deduction")
    no_deduction = RuleSet.from_dict(_v2(rules_data, deduction=None))
    assert no_deduction.moral.deduction is None


def test_negative_deduction_rejected() -> None:
    with pytest.raises(ValueError, match="moral_deduction 不能为负数"):
        ScoreInput(moral_deduction=D("-1"))
    with pytest.raises(TypeError):
        ScoreInput(moral_deduction=1.5)  # type: ignore[arg-type]


def test_direct_mode_ignores_deduction(v2: RuleSet) -> None:
    result = calculate(
        ScoreInput(quality_mode="direct", quality_direct=D("80"), moral_deduction=D("5")), v2
    )
    assert result.moral_total is None
    assert result.quality_total == D("80")
