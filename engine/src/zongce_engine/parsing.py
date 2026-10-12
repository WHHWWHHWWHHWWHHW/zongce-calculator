"""评议名单文本解析，兼容 legacy 的两种写法（CLAUDE.md §4.3.3）。"""

import re
from decimal import Decimal

# JavaScript 正则 \s 匹配的字符（ECMAScript WhiteSpace + LineTerminator），
# 与 Python 的 \s 不同：含全角空格、NBSP、BOM，不含 \x1c–\x1f。
_JS_WHITESPACE = "\t\n\v\f\r    -     　﻿"
_SEPARATORS = re.compile(f"[,，{_JS_WHITESPACE}]+")
# JavaScript parseFloat 识别的最长前缀（StrDecimalLiteral）；数字只认 ASCII 0–9。
_JS_FLOAT_PREFIX = re.compile(r"[+-]?(?:Infinity|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)")
_IMPORT_NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")


class NonFiniteInputError(ValueError):
    """输入中出现无穷大。legacy 会把它当作数值参与计算，引擎不支持。"""


def _parse_float_prefix(token: str) -> Decimal | None:
    match = _JS_FLOAT_PREFIX.match(token)
    if match is None:
        return None
    literal = match.group()
    if literal.lstrip("+-") == "Infinity":
        raise NonFiniteInputError(f"评议名单中不支持无穷大：{token!r}")
    return Decimal(literal)


def parse_rating_text(text: str) -> list[Decimal]:
    """复现 legacy 评议名单文本框的解析。

    legacy：``raw.split(/[,，\\s]+/).map(s => parseFloat(s)).filter(n => !isNaN(n))``。
    每段取 parseFloat 能识别的最长数字前缀（如 ``"9abc"`` → 9），识别不了的段丢弃。
    """
    values: list[Decimal] = []
    for token in _SEPARATORS.split(text):
        value = _parse_float_prefix(token)
        if value is not None:
            values.append(value)
    return values


def extract_numbers(text: str) -> list[Decimal]:
    """复现 legacy 表格导入的取数：``String(str).match(/-?\\d+(\\.\\d+)?/g).map(Number)``。"""
    return [Decimal(m) for m in _IMPORT_NUMBER.findall(text)]
