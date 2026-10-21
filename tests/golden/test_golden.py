"""黄金用例 G1–G3：引擎结果必须与 legacy 期望值完全一致（CLAUDE.md §5）。"""

from typing import Any

import pytest

from support.cases import displayed, load_golden, load_rules, to_score_input
from zongce_engine import calculate

RULES = load_rules()


@pytest.mark.parametrize("case", load_golden(), ids=lambda c: str(c["id"]))
def test_golden_case(case: dict[str, Any]) -> None:
    result = calculate(to_score_input(case["input"]), RULES)
    assert displayed(result) == case["expected"]
