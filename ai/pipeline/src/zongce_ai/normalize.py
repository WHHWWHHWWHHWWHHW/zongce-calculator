"""文本规范化：全角转半角、去空白、取数。"""

import re
import unicodedata
from decimal import Decimal

_SPACE = re.compile(r"\s+")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def compact(text: str) -> str:
    """NFKC（全角数字、字母、括号转半角）后去掉所有空白。"""
    return _SPACE.sub("", unicodedata.normalize("NFKC", text))


def student_id(text: str) -> tuple[str, bool]:
    """规范化学号，返回 (学号, 原文是否已经规范)。"""
    value = compact(text).upper()
    return value, value == text


def number(text: str) -> tuple[Decimal | None, bool]:
    """取单元格中唯一的数字，返回 (数值, 单元格是否只有这个数字)。有多个数字时不取。"""
    value = compact(text)
    found = _NUMBER.findall(value)
    if len(found) != 1:
        return None, False
    return Decimal(found[0]), found[0] == value
