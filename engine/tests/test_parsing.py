"""评议名单文本解析（与 legacy 两种写法保持一致，CLAUDE.md §4.3.3）。"""

from decimal import Decimal as D

import pytest

from zongce_engine.parsing import NonFiniteInputError, extract_numbers, parse_rating_text


def _ds(*values: str) -> list[D]:
    return [D(v) for v in values]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("9，1，2", _ds("9", "1", "2")),  # 全角逗号
        ("8 6 7", _ds("8", "6", "7")),
        ("9, 8.5,10", _ds("9", "8.5", "10")),
        ("  ,9,,8， \n7\t", _ds("9", "8", "7")),  # 首尾和连续分隔符
        ("9　8 7﻿6", _ds("9", "8", "7", "6")),  # JS \s 包含全角空格、NBSP、BOM
        ("9\x1c8", _ds("9")),  # \x1c 不是 JS 空白：整段交给 parseFloat，只取前缀 9
        ("9abc 8", _ds("9", "8")),  # parseFloat 取最长数字前缀
        ("abc", []),
        ("", []),
        (".5 5. 1e1 1.e1 2E-1 +3 -4", _ds("0.5", "5", "10", "10", "0.2", "3", "-4")),
        ("1e 1e+ 7e-x", _ds("1", "1", "7")),  # 指数不完整时只取前面的数字
        ("- + .", []),
        ("１２ 3", _ds("3")),  # 全角数字不被 parseFloat 识别
        ("0x10", _ds("0")),
    ],
)
def test_parse_rating_text(text: str, expected: list[D]) -> None:
    assert parse_rating_text(text) == expected


@pytest.mark.parametrize("text", ["Infinity", "9, -Infinity", "+Infinityx"])
def test_parse_rating_text_rejects_infinity(text: str) -> None:
    with pytest.raises(NonFiniteInputError):
        parse_rating_text(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("9，1，2", _ds("9", "1", "2")),
        ("8 6 7", _ds("8", "6", "7")),
        ("a-1.5b2.c", _ds("-1.5", "2")),
        ("1e5", _ds("1", "5")),
        (".5", _ds("5")),
        ("--3", _ds("-3")),
        ("１２", []),
        ("", []),
    ],
)
def test_extract_numbers(text: str, expected: list[D]) -> None:
    assert extract_numbers(text) == expected
