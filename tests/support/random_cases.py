"""对拍用随机用例生成器（可复现：固定种子即固定用例）。

覆盖 CLAUDE.md §5.1 要求：空值、边界值 0/59/60/封顶值、评议名单人数 1–60；
另外覆盖直接输入总分模式、超出范围的输入、全角/空白等多种名单分隔符。
"""

import random
from decimal import Decimal
from typing import Any

MORAL_ITEMS = (("political", 10), ("morality", 10), ("discipline", 5), ("integrity", 5))
SEPARATORS = (",", "，", " ", ", ", "，", "\n", "\t", "  ", " ，", ",\n")
MAX_LIST_SIZE = 60


def _decimal(rng: random.Random, low: int, high: int, places: int) -> str:
    """[low, high] 内随机取 places 位小数的十进制字符串。"""
    scale = 10**places
    value = Decimal(rng.randint(low * scale, high * scale)).scaleb(-places)
    return format(value, "f")


def _pick(rng: random.Random, empty: float, boundaries: tuple[str, ...], random_value: str) -> str:
    roll = rng.random()
    if roll < empty:
        return ""
    if roll < empty + 0.25:
        return rng.choice(boundaries)
    return random_value


def _ratings_text(rng: random.Random, size: int, maximum: int) -> str:
    values = []
    for _ in range(size):
        if rng.random() < 0.03:  # 偶尔出现超出范围的打分
            values.append(rng.choice(["-1", str(maximum + 1), "0", str(maximum)]))
        else:
            values.append(_decimal(rng, 0, maximum, rng.choice((0, 1, 1, 2))))
    sep = rng.choice(SEPARATORS)
    text = sep.join(values)
    if rng.random() < 0.1:
        text = rng.choice(SEPARATORS) + text + rng.choice(SEPARATORS)
    return text


def _moral_item(rng: random.Random, maximum: int, forced_size: int | None) -> dict[str, str]:
    roll = rng.random()
    if forced_size is not None or roll >= 0.45:
        size = forced_size if forced_size is not None else rng.randint(1, MAX_LIST_SIZE)
        return {"mode": "list", "text": _ratings_text(rng, size, maximum)}
    if roll < 0.12:
        return {"mode": "direct", "value": ""}
    boundaries = ("0", str(maximum), f"{maximum}.5", str(maximum + 2), "-1")
    value = _pick(rng, 0, boundaries, _decimal(rng, 0, maximum, rng.choice((0, 1, 2))))
    return {"mode": "direct", "value": value}


def _random_input(rng: random.Random, index: int) -> dict[str, Any]:
    gpa = _pick(
        rng,
        0.04,
        ("0", "5", "1", "4.0", "3.0001", "4.9999"),
        _decimal(rng, 1, 5, rng.choice((2, 4, 4, 4))),
    )
    data: dict[str, Any] = {
        "gpa": gpa,
        "quality_mode": "direct" if rng.random() < 0.08 else "detail",
        "quality_direct": _pick(
            rng,
            0.1,
            ("0", "100", "100.5", "120", "-5", "60"),
            _decimal(rng, 0, 100, rng.choice((0, 2, 4))),
        ),
    }
    for position, (name, maximum) in enumerate(MORAL_ITEMS):
        # 前 60 个用例的政治素养依次使用 1–60 人的评议名单，保证每个人数都被覆盖
        forced = index + 1 if position == 0 and index < MAX_LIST_SIZE else None
        data[name] = _moral_item(rng, maximum, forced)
    data["second_classroom"] = _pick(
        rng,
        0.1,
        ("0", "0.5", "9.99", "10", "10.01", "20", "-1"),
        _decimal(rng, 0, 15, rng.choice((0, 1, 2))),
    )
    data["public_service"] = _pick(
        rng, 0.1, ("0", "1", "9", "10", "11", "-2"), str(rng.randint(0, 15))
    )
    for name in ("fitness_test", "dorm_check"):
        data[name] = _pick(
            rng,
            0.1,
            ("0", "59", "59.9", "59.99", "60", "60.01", "100"),
            _decimal(rng, 0, 100, rng.choice((0, 1))),
        )
    data["ability"] = _pick(
        rng,
        0.1,
        ("0", "50", "50.5", "49.9999", "60", "-3"),
        _decimal(rng, 0, 50, rng.choice((0, 1, 2, 4))),
    )
    return data


def generate_cases(count: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [{"id": f"R{i:05d}", "input": _random_input(rng, i)} for i in range(count)]
