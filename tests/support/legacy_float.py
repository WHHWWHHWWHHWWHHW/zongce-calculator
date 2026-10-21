"""用 IEEE 754 双精度（Python float 与 JavaScript number 相同）逐步模拟 legacy calc()。

只用于测试：解释对拍差异的来源（docs/adr/0002）。引擎本身禁止使用 float。
运算顺序与 legacy 源码一致：parseFloat、去极值平均的逐项累加、clamp、
round4 = Math.round((v + Number.EPSILON) * 10000) / 10000、toFixed(4)。
"""

import math
import re
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

_EPSILON = 2.0**-52  # Number.EPSILON
_JS_FLOAT_PREFIX = re.compile(r"[+-]?(?:Infinity|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)")
_SEPARATORS = re.compile("[,，\t\n\v\f\r    -     　﻿]+")
_MORAL = (("political", 10.0), ("morality", 10.0), ("discipline", 5.0), ("integrity", 5.0))


def _parse_float(text: str | None) -> float:
    match = _JS_FLOAT_PREFIX.match(text or "")
    return float(match.group()) if match else math.nan


def _or_zero(value: float) -> float:
    return 0.0 if math.isnan(value) or value == 0 else value


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _math_round(value: float) -> float:
    # JS Math.round：取最接近的整数，.5 向正无穷；floor(x + 0.5) 在 x 接近 0.5 时有误差，需单独处理
    floor = math.floor(value)
    return float(floor + 1) if value - floor >= 0.5 else float(floor)


def _to_fixed4(value: float) -> str:
    # JS toFixed(4)：对 double 的精确十进制值四舍五入（恰为 .5 时远离 0）；-0 显示为 0
    exact = Decimal(value) if value != 0 else Decimal(0)
    return format(exact.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")


def _trimmed_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    k = int(_math_round(n * 0.1))
    if k * 2 >= n:
        k = max(0, (n - 1) // 2)
    total = 0.0
    for value in ordered[k : n - k]:
        total += value
    return total / (n - 2 * k)


def _moral_score(item: Mapping[str, str], maximum: float) -> float:
    if item["mode"] == "list":
        parsed = (_parse_float(t) for t in _SEPARATORS.split(item.get("text", "")))
        return _clamp(_trimmed_mean([v for v in parsed if not math.isnan(v)]), 0.0, maximum)
    value = _parse_float(item.get("value"))
    return 0.0 if math.isnan(value) else _clamp(value, 0.0, maximum)


def legacy_display(data: Mapping[str, Any]) -> dict[str, str | None]:
    """返回 legacy 页面应显示的 5 个结果（与 tests/support/cases.displayed 键相同）。"""
    gpa = _or_zero(_parse_float(data.get("gpa")))
    moral: float | None = None
    competence: float | None = None
    if data.get("quality_mode") == "direct":
        quality = _clamp(_or_zero(_parse_float(data.get("quality_direct"))), 0.0, 100.0)
    else:
        moral_sum = 0.0
        for name, maximum in _MORAL:
            moral_sum += _moral_score(data[name], maximum)
        moral = _clamp(moral_sum, 0.0, 30.0)
        second = min(_or_zero(_parse_float(data.get("second_classroom"))) * 0.5, 5.0)
        service = min(_or_zero(_parse_float(data.get("public_service"))) * 0.5, 5.0)
        fitness = _parse_float(data.get("fitness_test"))
        dorm = _parse_float(data.get("dorm_check"))
        basic = (
            second
            + service
            + (5.0 if not math.isnan(fitness) and fitness >= 60 else 0.0)
            + (5.0 if not math.isnan(dorm) and dorm >= 60 else 0.0)
        )
        ability = _clamp(_or_zero(_parse_float(data.get("ability"))), 0.0, 50.0)
        competence = _clamp(basic + ability, 0.0, 70.0)
        quality = _clamp(moral + competence, 0.0, 100.0)
    final = _math_round((quality / 20 * 0.25 + gpa * 0.75 + _EPSILON) * 10000) / 10000
    return {
        "final_score": _to_fixed4(final),
        "gpa": _to_fixed4(gpa),
        "quality_total": _to_fixed4(quality),
        "moral_total": None if moral is None else _to_fixed4(moral),
        "competence_total": None if competence is None else _to_fixed4(competence),
    }
