"""把表单中的获奖等级原文（如“省级 一等奖”“省一”“第五名”）对应到申报目录某一项目的选项。

做法是规则匹配，不调用大模型：
1. 原文就是选项编码 → 置信度 1；
2. 项目只有一个选项 → 置信度 1；
3. 拆出“维度”（赛事类别、级别、奖项、名次、个人/接力）。选项限定的每个维度，原文都必须落在
   选项允许的范围内；满足条件且限定维度最多的选项唯一时采用；
4. 按选项名称中的称号（以“、”分隔）在原文中查找，最长的唯一匹配采用。
不唯一或找不到时不猜，交给人工。
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .normalize import compact

_CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_PAREN = re.compile(r"\((?:含|每人|[A-Z])[^)]*\)")

# 原文改写：缩写与同义词统一成标准说法（按顺序执行）
_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    # “省一”“国二”等缩写：后面紧跟“奖”、非汉字或结尾时才改写，避免误伤“全国三好学生”
    (re.compile(r"(国|省|校|院)([一二三])(?=$|奖|[^\u4e00-\u9fff])"), r"\1级\2等奖"),
    (re.compile(r"(国|省|校|院)(?=[特一二三]等)"), r"\1级"),  # “省一等奖”
    (re.compile(r"金奖"), "一等奖"),
    (re.compile(r"银奖"), "二等奖"),
    (re.compile(r"铜奖"), "三等奖"),
    (re.compile(r"([特一二三])等(?!奖)"), r"\1等奖"),
    (re.compile(r"国级|国家级|全国|国家"), "国家级"),
    (re.compile(r"省部级|省级|省赛|山东省"), "省级"),
    (re.compile(r"校级|校赛|济南大学"), "校级"),
    (re.compile(r"院级|院赛"), "院级"),
)
_LEVELS = ("国家级", "省级", "市级", "校级", "院级")
_LEVEL_ORDER = ("院级", "校级", "市级", "省级", "国家级")  # 用于“省级及以上”
_RANKS = ("特等奖", "一等奖", "二等奖", "三等奖", "优秀奖", "完成奖", "精神文明奖")
_CLASSES = re.compile(r"([一二三123])类")
_PLACE = re.compile(r"第([一二三四五六七八九1-9])(?:[-–~至到]([一二三四五六七八九1-9]))?名")

_FACET_WORDS = re.compile(
    "|".join((*_LEVELS, *_RANKS, r"[一二三123]类", "赛事", "及以上", r"第.名", "每人"))
)

CONFIDENT = Decimal("0.95")
LIKELY = Decimal("0.85")
ALIAS = Decimal("0.9")
AMBIGUOUS = Decimal("0.4")


@dataclass(frozen=True)
class OptionMatch:
    option_code: str | None
    confidence: Decimal
    reason: str


@dataclass(frozen=True)
class _Facets:
    classes: frozenset[int]
    levels: frozenset[str]
    ranks: frozenset[str]
    places: frozenset[int]
    events: frozenset[str]

    def dims(self) -> tuple[frozenset[Any], ...]:
        return (self.classes, self.levels, self.ranks, self.places, self.events)

    def constrained(self) -> int:
        return sum(1 for d in self.dims() if d)


def _digit(text: str) -> int:
    return _CN_DIGITS.get(text) or int(text)


def _standard(text: str) -> str:
    text = compact(text)
    for pattern, replacement in _REWRITES:
        text = pattern.sub(replacement, text)
    return text


def _facets(text: str, *, option: bool) -> _Facets:
    if option:
        text = _PAREN.sub("", compact(text))  # 去掉“（含金奖）”“（每人）”等说明
    text = _standard(text)
    levels = {lv for lv in _LEVELS if lv in text}
    if option and "省市级" in text:
        levels |= {"省级", "市级"}
    if option:
        for i, level in enumerate(_LEVEL_ORDER):
            if f"{level}及以上" in text:
                levels |= set(_LEVEL_ORDER[i:])
    ranks = {r for r in _RANKS if r in text}
    if option and "一等奖" in ranks and "及以上" in text:
        ranks.add("特等奖")
    places: set[int] = set()
    for first, last in _PLACE.findall(text):
        start = _digit(first)
        places.update(range(start, (_digit(last) if last else start) + 1))
    events = {e for e in ("个人", "接力") if e in text}
    return _Facets(
        classes=frozenset(_digit(c) for c in _CLASSES.findall(text)),
        levels=frozenset(levels),
        ranks=frozenset(ranks),
        places=frozenset(places),
        events=frozenset(events),
    )


def _fits(option: _Facets, row: _Facets) -> bool:
    """选项限定的每个维度，原文都有且落在允许范围内。"""
    return all(
        not allowed or (bool(found) and found <= allowed)
        for allowed, found in zip(option.dims(), row.dims(), strict=True)
    )


def _compatible(option: _Facets, row: _Facets) -> bool:
    """原文没有与选项矛盾的信息，且至少对上一个维度（可能缺少某些维度）。"""
    pairs = list(zip(option.dims(), row.dims(), strict=True))
    no_conflict = all(not allowed or not found or found <= allowed for allowed, found in pairs)
    return no_conflict and any(allowed and found for allowed, found in pairs)


def _unique_best(scored: list[tuple[int, str]]) -> tuple[str | None, int]:
    if not scored:
        return None, 0
    best = max(score for score, _ in scored)
    winners = [code for score, code in scored if score == best]
    return (winners[0] if len(winners) == 1 else None), len(winners)


def _meaningful(alias: str) -> bool:
    """去掉级别、奖项、类别等维度词后还剩至少 2 个字，才算称号（避免“一类”这样的片段误配）。"""
    return len(_FACET_WORDS.sub("", alias)) >= 2


def _by_alias(text: str, options: Sequence[tuple[str, str]]) -> OptionMatch | None:
    """按选项名称中的称号查找，最长的唯一匹配采用。"""
    plain = _standard(text)
    scored = []
    for option_code, name in options:
        parts = re.split(r"[、,，/]", _standard(_PAREN.sub("", name)))
        aliases = [a for a in parts if _meaningful(a)]
        lengths = [len(a) for a in aliases if a in plain]
        if lengths:
            scored.append((max(lengths), option_code))
    code, count = _unique_best(scored)
    if code is not None:
        return OptionMatch(code, ALIAS, "按称号名称匹配")
    if count > 1:
        return OptionMatch(None, AMBIGUOUS, "称号名称同时符合多个选项")
    return None


def match_option(text: str, options: Sequence[tuple[str, str]]) -> OptionMatch:
    """options 为 (选项编码, 选项名称)。"""
    plain = compact(text)
    codes = {code for code, _ in options}
    if plain in codes:
        return OptionMatch(plain, Decimal(1), "原文即选项编码")
    if len(options) == 1:
        return OptionMatch(options[0][0], Decimal(1), "项目只有一个选项")
    row = _facets(text, option=False)
    facets = {code: _facets(name, option=True) for code, name in options}
    scored = [(f.constrained(), c) for c, f in facets.items() if f.constrained() and _fits(f, row)]
    code, count = _unique_best(scored)
    if code is not None:
        exact = row.constrained() == facets[code].constrained()
        return OptionMatch(
            code,
            CONFIDENT if exact else LIKELY,
            "级别、奖项完全对应" if exact else "原文还有选项未涉及的信息",
        )
    if count > 1:
        # 多个选项同样符合（如称号类选项都写着“济南大学”），再按称号名称区分
        best = max(s for s, _ in scored)
        tied = [(c, n) for c, n in options if (best, c) in scored]
        alias = _by_alias(text, tied)
        if alias is not None and alias.option_code is not None:
            return alias
        return OptionMatch(None, AMBIGUOUS, "原文同时符合多个选项，缺少区分信息")
    alias = _by_alias(text, options)
    if alias is not None:
        return alias
    if any(_compatible(f, row) for f in facets.values()):
        return OptionMatch(None, AMBIGUOUS, "原文缺少区分信息（如赛事类别、级别或奖项）")
    return OptionMatch(None, Decimal(0), "无法对应到任何选项")
