"""数值工具：JS Math.round 语义、限幅、去极值平均、4 位小数展示。"""

from decimal import Decimal as D

import pytest

from zongce_engine.numbers import clamp, format_score, js_round, round_js, trimmed_mean


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", "0"),
        ("0.4999", "0"),
        ("0.5", "1"),
        ("1.5", "2"),
        ("2.5", "3"),  # Python round() 会得到 2（银行家舍入），JS Math.round 得到 3
        ("2.4999", "2"),
        ("-0.5", "0"),  # JS Math.round(-0.5) = -0 → 0
        ("-2.5", "-2"),  # .5 一律向正无穷进位
        ("-2.6", "-3"),
    ],
)
def test_js_round_matches_math_round(value: str, expected: str) -> None:
    assert js_round(D(value)) == D(expected)


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        ("3.7252375", 4, "3.7252"),
        ("4.65625", 4, "4.6563"),
        ("4.1", 4, "4.1000"),
        ("0", 4, "0.0000"),
        ("-1.00005", 4, "-1.0000"),  # 与 legacy round4 一致：Math.round(-10000.5) = -10000
        ("-0.00001", 4, "0.0000"),
    ],
)
def test_round_js(value: str, places: int, expected: str) -> None:
    result = round_js(D(value), places)
    assert str(result) == expected


def test_clamp() -> None:
    assert clamp(D("12"), D("0"), D("10")) == D("10")
    assert clamp(D("-1"), D("0"), D("10")) == D("0")
    assert clamp(D("7.25"), D("0"), D("10")) == D("7.25")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("3.72525", "3.7253"),  # 与 JS toFixed(4) 一致：恰为 .5 时远离 0
        ("5", "5.0000"),
        ("0", "0.0000"),
        ("-0", "0.0000"),  # JS (-0).toFixed(4) === "0.0000"
        ("-0.00001", "-0.0000"),  # JS (-0.00001).toFixed(4) === "-0.0000"
        ("-1.00005", "-1.0001"),
    ],
)
def test_format_score(value: str, expected: str) -> None:
    assert format_score(D(value)) == expected


def _ds(*values: str | int) -> tuple[D, ...]:
    return tuple(D(str(v)) for v in values)


def test_trimmed_mean_empty() -> None:
    result = trimmed_mean((), D("0.1"))
    assert (result.mean, result.count, result.trimmed_per_side) == (D("0"), 0, 0)


def test_trimmed_mean_g1_list() -> None:
    result = trimmed_mean(_ds("9", "8.5", "10", "7", "9.5", "8", "9", "10", "6.5", "8"), D("0.1"))
    assert result.mean == D("8.625")
    assert (result.count, result.trimmed_per_side) == (10, 1)


def test_trimmed_mean_n5_rounds_half_up() -> None:
    # n×0.1 = 0.5 → k = 1；误用银行家舍入会得到 k = 0、均值 4
    result = trimmed_mean(_ds(1, 2, 3, 4, 10), D("0.1"))
    assert result.mean == D("3")
    assert result.trimmed_per_side == 1


@pytest.mark.parametrize(
    ("n", "k"),
    [(1, 0), (3, 0), (4, 0), (5, 1), (14, 1), (15, 2), (24, 2), (25, 3), (35, 4), (60, 6)],
)
def test_trimmed_mean_k(n: int, k: int) -> None:
    result = trimmed_mean(_ds(*range(1, n + 1)), D("0.1"))
    assert result.trimmed_per_side == k
    kept = range(1 + k, n + 1 - k)
    assert result.mean == D(sum(kept)) / D(len(kept))


def test_trimmed_mean_sorts_input() -> None:
    result = trimmed_mean(_ds(10, 1, 3, 2, 4), D("0.1"))
    assert result.mean == D("3")


def test_trimmed_mean_non_terminating() -> None:
    result = trimmed_mean(_ds(1, 1, 2), D("0.1"))
    assert result.mean == D(4) / D(3)


@pytest.mark.parametrize(
    ("values", "k", "mean"),
    [
        # 比例 0.5 时会触发 legacy 的回退分支 if (2k >= n) k = max(0, floor((n-1)/2))
        ((1,), 0, "1"),
        ((1, 3), 0, "2"),
        ((1, 2, 3, 10), 1, "2.5"),
    ],
)
def test_trimmed_mean_fallback_branch(values: tuple[int, ...], k: int, mean: str) -> None:
    result = trimmed_mean(_ds(*values), D("0.5"))
    assert result.trimmed_per_side == k
    assert result.mean == D(mean)
