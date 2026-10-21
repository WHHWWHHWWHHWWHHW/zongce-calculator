"""与 legacy 页面对拍（CLAUDE.md §5.1）。

legacy 侧：jsdom 原样加载 zongce-calculator.html，填入输入框并调用页面自身的 calc()。
引擎侧：同一份输入经 zongce_engine 计算，按页面显示方式格式化为 4 位小数。
两侧显示的 5 个结果（综测成绩、GPA、综合素质、思想品德、综合能力）逐字比对。
唯一允许的差异是 legacy 二进制浮点在 .5 舍入边界少进位（负责人 2026-10-12 决定，见 docs/adr/0002）。

环境变量：PARITY_COUNT（默认 2000，不得少于 1000）、PARITY_SEED（默认 20261012）。
"""

import json
import os
import warnings
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from support.cases import DISPLAY_KEYS, displayed, load_golden, load_rules, to_score_input
from support.legacy import run_legacy
from support.legacy_float import legacy_display
from support.random_cases import MAX_LIST_SIZE, generate_cases
from zongce_engine import ScoreResult, calculate, parse_rating_text

COUNT = int(os.environ.get("PARITY_COUNT", "2000"))
SEED = int(os.environ.get("PARITY_SEED", "20261012"))
RULES = load_rules()


def test_random_cases_cover_required_ranges() -> None:
    cases = generate_cases(COUNT, SEED)
    assert len(cases) >= 1000
    inputs = [c["input"] for c in cases]
    sizes = {
        len(parse_rating_text(i["political"]["text"]))
        for i in inputs
        if i["political"]["mode"] == "list"
    }
    assert set(range(1, MAX_LIST_SIZE + 1)) <= sizes
    for name in ("fitness_test", "dorm_check"):
        assert {"", "0", "59", "60", "100"} <= {i[name] for i in inputs}
    assert {"", "0", "10", "20"} <= {i["second_classroom"] for i in inputs}
    assert {"", "0", "10", "11"} <= {i["public_service"] for i in inputs}
    assert {"", "0", "50", "60"} <= {i["ability"] for i in inputs}
    assert {"detail", "direct"} == {i["quality_mode"] for i in inputs}


@pytest.mark.parity
def test_golden_expected_values_come_from_legacy() -> None:
    cases = load_golden()
    for case, legacy in zip(cases, run_legacy(cases), strict=True):
        assert legacy["id"] == case["id"]
        assert {k: legacy[k] for k in DISPLAY_KEYS} == case["expected"]


class ParityKnownDifference(UserWarning):
    """已知差异：legacy 二进制浮点在 .5 舍入边界少进位（docs/adr/0002、rules-issues R-008）。"""


def _on_half_boundary(value: Decimal, places: int = 4) -> bool:
    """value 在第 places 位之后是否恰好为 5（十进制舍入边界）。"""
    scaled = value.scaleb(places)
    return scaled - scaled.to_integral_value(rounding="ROUND_FLOOR") == Decimal("0.5")


def _exact_values(result: ScoreResult) -> dict[str, Decimal | None]:
    return {
        "final_score": result.final_score_raw,
        "gpa": result.gpa,
        "quality_total": result.quality_total,
        "moral_total": result.moral_total,
        "competence_total": result.competence_total,
    }


def _is_known_float_difference(
    field: str, exact: Decimal | None, ours: str | None, theirs: str | None
) -> bool:
    """引擎按精确值进位、legacy 因二进制浮点少进 0.0001，且精确值恰在 .5 边界。"""
    if exact is None or ours is None or theirs is None:
        return False
    return _on_half_boundary(exact) and Decimal(ours) - Decimal(theirs) == Decimal("0.0001")


@pytest.mark.parity
def test_random_cases_match_legacy(tmp_path: Path) -> None:
    """除已知的浮点边界差异外，引擎与 legacy 必须 0 差异。

    已知差异必须同时满足：精确值恰在 .5 舍入边界；引擎比 legacy 多 0.0001；
    且双精度模拟器（tests/support/legacy_float.py）逐字复现了 legacy 的输出。
    双精度模拟器本身也必须对全部用例与 jsdom 中的 legacy 一致。
    """
    cases = generate_cases(COUNT, SEED)
    legacy_results = run_legacy(cases)
    known: list[dict[str, Any]] = []
    unexplained: list[dict[str, Any]] = []
    emulator_mismatches: list[str] = []
    for case, legacy in zip(cases, legacy_results, strict=True):
        assert legacy["id"] == case["id"]
        theirs = {k: legacy[k] for k in DISPLAY_KEYS}
        if legacy_display(case["input"]) != theirs:
            emulator_mismatches.append(case["id"])
        result = calculate(to_score_input(case["input"]), RULES)
        ours = displayed(result)
        if ours == theirs:
            continue
        exact = _exact_values(result)
        fields = [k for k in DISPLAY_KEYS if ours[k] != theirs[k]]
        entry = {
            "id": case["id"],
            "fields": fields,
            "engine": ours,
            "legacy": theirs,
            "exact": {k: None if v is None else str(v) for k, v in exact.items()},
            "input": case["input"],
        }
        explained = case["id"] not in emulator_mismatches and all(
            _is_known_float_difference(k, exact[k], ours[k], theirs[k]) for k in fields
        )
        (known if explained else unexplained).append(entry)

    report = tmp_path / "parity-report.json"
    report.write_text(
        json.dumps({"known": known, "unexplained": unexplained}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assert not emulator_mismatches, f"双精度模拟器与 legacy 不一致：{emulator_mismatches[:20]}"
    summary = "\n".join(
        f"  {m['id']} {m['fields']} engine={m['engine']} legacy={m['legacy']} exact={m['exact']}"
        for m in unexplained[:15]
    )
    assert not unexplained, (
        f"{len(unexplained)}/{len(cases)} 组存在无法解释的差异（种子 {SEED}），"
        f"完整清单：{report}\n{summary}"
    )
    final_known = sum("final_score" in m["fields"] for m in known)
    warnings.warn(
        ParityKnownDifference(
            f"{len(cases)} 组对拍：无法解释的差异 0；已知浮点边界差异 {len(known)} 组"
            f"（其中综测成绩 {final_known} 组），详见 {report}"
        ),
        stacklevel=1,
    )
