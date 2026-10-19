"""规则文件解析与校验。"""

import copy
import json
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from zongce_engine import RuleError, RuleSet
from zongce_engine.rules import LinearCappedRule, ThresholdRule


def test_v1_matches_schema(rules_data: dict[str, Any], schema_data: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator.check_schema(schema_data)
    jsonschema.Draft202012Validator(schema_data).validate(rules_data)


def test_v1_has_no_json_floats(rules_path: Path) -> None:
    # 数值一律为字符串，避免 JSON 解析成 float（CLAUDE.md §10）
    def no_float(value: str) -> Any:
        raise AssertionError(f"规则文件中出现 JSON 浮点数：{value}")

    json.loads(rules_path.read_text(encoding="utf-8"), parse_float=no_float)


def test_v1_values(rules: RuleSet) -> None:
    assert (rules.id, rules.version) == ("ujn-v1", "1.0.0")
    assert rules.final.academic_weight == D("0.75")
    assert rules.final.quality_weight == D("0.25")
    assert rules.final.quality_divisor == D("20")
    assert rules.final.decimal_places == 4
    assert rules.final.intermediate_decimal_places is None  # v1：中间值不舍入（legacy）
    assert (rules.quality.min, rules.quality.max) == (D("0"), D("100"))
    assert (rules.quality.direct.min, rules.quality.direct.max) == (D("0"), D("100"))
    assert (rules.moral.min, rules.moral.max) == (D("0"), D("30"))
    assert rules.moral.trim.ratio == D("0.1")
    assert [(i.field, i.max) for i in rules.moral.items] == [
        ("political", D("10")),
        ("morality", D("10")),
        ("discipline", D("5")),
        ("integrity", D("5")),
    ]
    assert (rules.competence.min, rules.competence.max) == (D("0"), D("70"))
    assert (rules.competence.ability.min, rules.competence.ability.max) == (D("0"), D("50"))
    second, service, fitness, dorm = rules.competence.basic
    assert isinstance(second, LinearCappedRule)
    assert (second.field, second.rate, second.cap) == ("second_classroom", D("0.5"), D("5"))
    assert isinstance(service, LinearCappedRule)
    assert (service.field, service.rate, service.cap) == ("public_service", D("0.5"), D("5"))
    assert isinstance(fitness, ThresholdRule)
    assert (fitness.field, fitness.threshold, fitness.points) == ("fitness_test", D("60"), D("5"))
    assert isinstance(dorm, ThresholdRule)
    assert (dorm.field, dorm.threshold, dorm.points) == ("dorm_check", D("60"), D("5"))


def test_every_rule_has_unique_id_and_source(rules: RuleSet) -> None:
    all_rules = rules.all_rules()
    ids = [r.id for r in all_rules]
    assert len(ids) == len(set(ids)) == 16
    assert all(r.source.strip() for r in all_rules)


_DELETE = object()


def _mutate(data: dict[str, Any], path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    result = copy.deepcopy(data)
    target: Any = result
    for key in path[:-1]:
        target = target[key]
    if value is _DELETE:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return result


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("final",), _DELETE, "final: 缺少"),
        (("final", "academic_weight"), 0.75, "final.academic_weight"),
        (("final", "academic_weight"), "1e3", "final.academic_weight"),
        (("final", "decimal_places"), "4", "final.decimal_places"),
        (("final", "decimal_places"), True, "final.decimal_places"),
        (("final", "decimal_places"), 11, "final.decimal_places"),
        (("final", "intermediate_decimal_places"), "4", "final.intermediate_decimal_places"),
        (("final", "intermediate_decimal_places"), 11, "final.intermediate_decimal_places"),
        (("final", "rounding"), "half_even", "final.rounding"),
        (("final", "quality_divisor"), "0", "final.quality_divisor"),
        (("final", "id"), "Final!", "final.id"),
        (("final", "id"), 3, "final.id"),
        (("final", "source"), "  ", "final.source"),
        (("final", "name"), 3, "final.name"),
        (("version",), "1.0", "version"),
        (("academic",), [], "academic"),
        (("moral", "items"), [], "moral.items"),
        (("moral", "items"), {}, "moral.items"),
        (("moral", "items", 0, "field"), "politics", "moral.items[0].field"),
        (("moral", "items", 1, "field"), "political", "moral.items[1].field"),
        (("moral", "trim", "ratio"), "0.6", "moral.trim.ratio"),
        (("moral", "min"), "40", "moral"),
        (("competence", "basic", 0, "type"), "step", "competence.basic[0].type"),
        (("competence", "basic", 0, "field"), "ability", "competence.basic[0].field"),
        (("competence", "basic", 1, "field"), "second_classroom", "competence.basic[1].field"),
        (("competence", "ability", "field"), "abilities", "competence.ability.field"),
        (("quality", "direct", "id"), "moral", "重复的规则 id"),
    ],
)
def test_invalid_rules_rejected(
    rules_data: dict[str, Any], path: tuple[str | int, ...], value: object, message: str
) -> None:
    with pytest.raises(RuleError, match=message.replace("[", r"\[").replace("]", r"\]")):
        RuleSet.from_dict(_mutate(rules_data, path, value))


def test_top_level_must_be_object() -> None:
    with pytest.raises(RuleError, match="规则文件"):
        RuleSet.from_dict(["not", "an", "object"])


def test_rule_error_is_value_error() -> None:
    assert issubclass(RuleError, ValueError)


def test_intermediate_places_optional(
    rules_data: dict[str, Any], schema_data: dict[str, Any]
) -> None:
    # R-005 的备选口径：中间值也舍入到 4 位。可选字段，缺省（null）即 legacy 口径
    data = _mutate(rules_data, ("final", "intermediate_decimal_places"), 4)
    assert RuleSet.from_dict(data).final.intermediate_decimal_places == 4
    jsonschema.validate(data, schema_data)
    data = _mutate(rules_data, ("final", "intermediate_decimal_places"), None)
    assert RuleSet.from_dict(data).final.intermediate_decimal_places is None
    jsonschema.validate(data, schema_data)
