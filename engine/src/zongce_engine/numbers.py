"""数值工具。所有函数只接受和返回 Decimal。"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

ZERO = Decimal(0)
_HALF = Decimal("0.5")


def js_round(value: Decimal) -> Decimal:
    """与 JavaScript ``Math.round`` 相同：``floor(x + 0.5)``。

    .5 一律向正无穷进位（2.5 → 3，-2.5 → -2）。对非负数即通常的四舍五入；
    与 Python 内置 ``round()`` 的银行家舍入不同（CLAUDE.md §4.3）。
    """
    return (value + _HALF).to_integral_value(rounding=ROUND_FLOOR)


def round_js(value: Decimal, places: int) -> Decimal:
    """按 ``js_round`` 语义保留 ``places`` 位小数，复现 legacy 的 ``round4``。

    legacy 在 ``Math.round`` 前加 ``Number.EPSILON`` 以抵消二进制浮点误差；
    Decimal 是精确十进制，不需要也不加这一项。
    """
    quantum = Decimal(1).scaleb(-places)
    return js_round(value.scaleb(places)).scaleb(-places).quantize(quantum)


def clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    """与 legacy ``clamp`` 相同：``max(low, min(high, value))``。"""
    return max(low, min(high, value))


def format_score(value: Decimal, places: int = 4) -> str:
    """展示用字符串，与 JavaScript ``toFixed(places)`` 一致（恰为 .5 时远离 0 进位）。"""
    value = value.copy_abs() if value.is_zero() else value
    return format(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), "f")


@dataclass(frozen=True, slots=True)
class TrimmedMean:
    """去极值平均的结果。"""

    mean: Decimal
    count: int
    trimmed_per_side: int


def trimmed_mean(values: Sequence[Decimal], ratio: Decimal) -> TrimmedMean:
    """去掉两端各 ``ratio`` 比例后求平均，逐步复现 legacy ``trimmedMean``。

    1. 升序排序，n 为人数；n = 0 时结果为 0；
    2. 每端去掉 k = js_round(n × ratio) 个；
    3. 若 2k ≥ n，则 k = max(0, floor((n − 1) / 2))（ratio = 0.1 时不会触发）；
    4. 对剩余的数求算术平均。此时至少剩 1 个数，legacy 中“剩余为空返回 0”的判断不可达，故省略。
    """
    n = len(values)
    if n == 0:
        return TrimmedMean(ZERO, 0, 0)
    ordered = sorted(values)
    k = int(js_round(Decimal(n) * ratio))
    if 2 * k >= n:
        k = max(0, (n - 1) // 2)
    kept = ordered[k : n - k]
    return TrimmedMean(sum(kept, ZERO) / Decimal(len(kept)), n, k)
