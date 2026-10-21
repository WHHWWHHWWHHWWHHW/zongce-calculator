"""解析学院各部门的“活动获奖名单”文字（团委、学习部、文艺部、管服等的综测汇总）。

真实名单的写法（2025–2026 学年样本，已脱敏）：

    活动名称： 新生辩论赛
    第一名:2 分
    智能 2501 张三 智能 2501 李四 集成 2501 王五
    二等奖
    1.5分
    计科2501赵六 网合25w3钱七
    参赛人员： 3分(健脊操一等奖)
    孙八 周九 吴十
    学 36-424-郑一 学 23-211 王二

即：活动名称 → 等级与分值（可能分两行写）→ 一串“班级 姓名”、只有姓名，或“宿舍号-姓名”。
没有学号，所以后续要按“班级 + 姓名”或只按姓名找到学生（见 matching.resolve_students）。
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .names import CJK, DEFAULT_MAJORS, find_class_names, name_list
from .options import OptionMatch, compatible_options, has_level, match_option, names_present

_ACTIVITY = re.compile(r"^活动名称\s*[:：]\s*(?P<name>.+)$")
_TITLE = re.compile(r"^[“\"「].{2,40}[”\"」].*名单$|^.{4,40}获奖名单$")
_NOTE = re.compile(r"^获奖情况\s*[:：]\s*(?P<note>.+)$")
_LEVEL_WORDS = (
    r"(?:[特一二三四五六七八]等奖|第[一二三四五六七八1-8]名|优秀奖"
    r"|最佳[^\s:：\d]{1,6}|[^\s:：\d]{2,4}人员)"
)
_LEVEL_POINTS = re.compile(
    rf"^(?P<label>{_LEVEL_WORDS})\s*[:：]?\s*(?P<points>\d+(?:\.\d+)?)\s*分"
    r"\s*(?:[(（](?P<extra>[^)）]*)[)）])?$"
)
_LEVEL_ONLY = re.compile(rf"^(?P<label>{_LEVEL_WORDS})\s*[:：]?$")
_POINTS_ONLY = re.compile(r"^(?P<points>\d+(?:\.\d+)?)\s*分$")
_PSEUDONYM = r"学生\d{4}"
_NAME = rf"(?:{_PSEUDONYM}|[{CJK}]{{2,4}})"
_DORM_NAME = re.compile(rf"学?\s*\d{{1,2}}-\d{{3}}[-\s]*(?P<name>{_NAME})")


@dataclass(frozen=True)
class ActivityEntry:
    activity: str
    level: str  # 一等奖、第一名、参赛人员、工作人员、最佳辩手……
    points: Decimal | None
    note: str  # 获奖情况或括号里的说明，如“健脊操一等奖”“校第一名”
    class_code: str | None
    name: str
    line: int  # 在原文中的行号（从 1 开始）


@dataclass(frozen=True)
class ActivityList:
    entries: tuple[ActivityEntry, ...]
    activities: int
    partial_lines: tuple[int, ...]  # 名单行中还有没认出的内容（需要人工看）


def _join_wrapped(lines: list[str], majors: tuple[str, ...]) -> list[tuple[int, str]]:
    """把被换行截断的班级接回去：“…王五 集” + “成2501赵六…” → “…王五 集成2501赵六…”。"""
    major = "|".join(re.escape(m) for m in majors)
    joined: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        if joined:
            prev_number, prev = joined[-1]
            tail = re.search(rf"([{CJK}]{{1,3}})$", prev)
            if tail and re.match(rf"^(?:{major})\s?\d", tail.group(1) + line):
                joined[-1] = (prev_number, prev + line)
                continue
        joined.append((number, line))
    return joined


def _people(line: str, majors: tuple[str, ...]) -> tuple[list[tuple[str | None, str]], bool]:
    """一行名单中的 (班级, 姓名)；第二个值表示是否还有没认出的内容。"""
    found: list[tuple[str | None, str]] = []
    rest = line
    for pair in find_class_names(line, majors):
        found.append((pair.class_code, pair.name))
        rest = rest.replace(line[pair.start : pair.end], " ", 1)
    for dorm in _DORM_NAME.finditer(rest):
        found.append((None, dorm.group("name")))
    rest = _DORM_NAME.sub(" ", rest)
    leftovers = [t for t in re.split(r"[\s,，、;；]+", rest) if t]
    listed = name_list(" ".join(leftovers)) if leftovers else []
    if listed is not None:
        found.extend((None, n) for n in listed)
        leftovers = []
    else:
        names = [t for t in leftovers if re.fullmatch(_NAME, t)]
        lone_word = not found and len(names) == 1 and not re.fullmatch(_PSEUDONYM, names[0])
        if lone_word:  # 只有一个 2–4 字的词（如“心理协会”），是标题不是名单
            return [], False
        found.extend((None, n) for n in names)
        leftovers = [t for t in leftovers if t not in names]
    return found, bool(leftovers)


def parse_activity_list(text: str, majors: tuple[str, ...] = DEFAULT_MAJORS) -> ActivityList:
    lines = [unicodedata.normalize("NFKC", line).strip() for line in text.splitlines()]
    activity, level, note, activity_note = "", "", "", ""
    points: Decimal | None = None
    entries: list[ActivityEntry] = []
    partial: list[int] = []
    activities = 0
    for number, line in _join_wrapped(lines, majors):
        if not line:
            continue
        if m := _ACTIVITY.match(line):
            activity, level, note, points = m.group("name").strip(), "", "", None
            activity_note = ""
            activities += 1
        elif _TITLE.match(line) and not find_class_names(line, majors):
            activity, level, note, points = line, "", "", None
            activity_note = ""
            activities += 1
        elif m := _NOTE.match(line):
            activity_note = note = m.group("note").strip()
        elif m := _LEVEL_POINTS.match(line):
            level, points = m.group("label"), Decimal(m.group("points"))
            note = " ".join(t for t in (activity_note, m.group("extra")) if t)
        elif m := _LEVEL_ONLY.match(line):
            level, points = m.group("label"), None
        elif m := _POINTS_ONLY.match(line):
            points = Decimal(m.group("points"))
        else:
            people, leftover = _people(line, majors)
            if not people:
                continue  # 部门名、学院名等标题行
            if leftover:
                partial.append(number)
            entries.extend(
                ActivityEntry(activity, level, points, note, code, name, number)
                for code, name in people
            )
    return ActivityList(tuple(entries), activities, tuple(partial))


@dataclass(frozen=True)
class CatalogChoice:
    item_code: str
    option_code: str | None
    confidence: Decimal
    reason: str


def choose_item(
    entry: ActivityEntry,
    items: Sequence[tuple[str, Sequence[tuple[str, str, str]], str | None]],
    *,
    default_level: str = "院级",
) -> CatalogChoice | None:
    """按名单给出的分值和等级，选出对应的申报项目与选项。

    items：(项目编码, [(选项编码, 选项名称, 分值)], 按次计分时的每次分值)。
    先找分值相同的选项；有多个时，用等级名称（如“最佳辩手”）、等级文字和活动级别区分。
    名单和活动名称都没写级别时，按 default_level（学院各部门组织的活动为“院级”）判断。
    仍不唯一就不选，交给人工。
    """
    if entry.points is None:
        return None
    text = f"{entry.level} {entry.note} {entry.activity}"
    if not has_level(text):
        text += f" {default_level}"
    for item_code, options, unit_score in items:
        same = [(c, n) for c, n, score in options if Decimal(score) == entry.points]
        if len(same) == 1:
            return CatalogChoice(item_code, same[0][0], Decimal("0.95"), "分值唯一对应")
        if same:
            named = [c for c, n in same if len(entry.level) >= 2 and entry.level in n]
            if len(named) == 1:
                return CatalogChoice(item_code, named[0], Decimal("0.9"), "分值与等级名称对应")
            same = [(c, n) for c, n in same if names_present(text, n)]  # 称号类选项要写明称号
            picked: OptionMatch = match_option(text, same)
            if picked.option_code is not None:
                return CatalogChoice(
                    item_code, picked.option_code, picked.confidence, picked.reason
                )
            fit = compatible_options(text, same)
            if len(fit) == 1:
                return CatalogChoice(
                    item_code, fit[0], Decimal("0.85"), "分值相同的选项中只有它与级别不矛盾"
                )
            return CatalogChoice(item_code, None, Decimal("0.4"), "分值对应多个选项，需人工判断")
        if unit_score is not None and Decimal(unit_score) == entry.points:
            return CatalogChoice(item_code, None, Decimal("0.95"), "按次计分")
    return None
