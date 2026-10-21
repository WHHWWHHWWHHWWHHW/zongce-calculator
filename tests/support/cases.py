"""用例格式（tests/golden/cases.json）与引擎输入、输出之间的转换。"""

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

from zongce_engine import (
    MoralValue,
    PeerRatings,
    RuleSet,
    ScoreInput,
    ScoreResult,
    format_score,
    parse_rating_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASES = REPO_ROOT / "tests" / "golden" / "cases.json"
RULES_V1 = REPO_ROOT / "rules" / "ujn-v1.json"
DISPLAY_KEYS = ("final_score", "gpa", "quality_total", "moral_total", "competence_total")


def load_rules() -> RuleSet:
    return RuleSet.from_dict(json.loads(RULES_V1.read_text(encoding="utf-8")))


def load_golden() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads(GOLDEN_CASES.read_text(encoding="utf-8"))["cases"]
    return cases


def _number(value: str | None) -> Decimal | None:
    """页面数字输入框的值：空串表示未填写。"""
    return None if value is None or value == "" else Decimal(value)


def _moral(item: Mapping[str, str] | None) -> MoralValue:
    if item is None:
        return None
    if item["mode"] == "list":
        return PeerRatings(tuple(parse_rating_text(item.get("text", ""))))
    return _number(item.get("value"))


def to_score_input(data: Mapping[str, Any]) -> ScoreInput:
    """把用例的 input（页面上填写的字符串）转换为引擎输入。"""
    return ScoreInput(
        gpa=_number(data.get("gpa")),
        quality_mode=data.get("quality_mode", "detail"),
        quality_direct=_number(data.get("quality_direct")),
        political=_moral(data.get("political")),
        morality=_moral(data.get("morality")),
        discipline=_moral(data.get("discipline")),
        integrity=_moral(data.get("integrity")),
        second_classroom=_number(data.get("second_classroom")),
        public_service=_number(data.get("public_service")),
        fitness_test=_number(data.get("fitness_test")),
        dorm_check=_number(data.get("dorm_check")),
        ability=_number(data.get("ability")),
    )


def displayed(result: ScoreResult) -> dict[str, str | None]:
    """引擎结果按 legacy 页面的显示方式格式化（4 位小数）。"""

    def fmt(value: Decimal | None) -> str | None:
        return None if value is None else format_score(value)

    return {
        "final_score": fmt(result.final_score),
        "gpa": fmt(result.gpa),
        "quality_total": fmt(result.quality_total),
        "moral_total": fmt(result.moral_total),
        "competence_total": fmt(result.competence_total),
    }
