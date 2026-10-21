"""从学院名单的文字中找出“班级 + 姓名”。

学院各部门的获奖名单大多没有学号，写法是“计科 2501 张三 网合25W3李四……”。班级由专业简称加
年级班号组成（如 计科2501、网合25W3、人工智能2503）。专业简称取自已知班级（如到梦空间学分表的
“班级”列），这样才能在“张三网安2401”这种没有空格的写法里正确断开。
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

CJK = "一-鿿"
# 年级班号：两位年级 + 可选字母 + 一到两位班号（2501、25W3、23H3）
_CLASS_NUMBER = r"\d{2}[A-Za-z]?\d{1,2}"
_CLASS = re.compile(rf"^([{CJK}]{{2,6}})\s?({_CLASS_NUMBER})$")
# 默认专业简称（信息学院常见写法）；实际使用时应由已知班级补充
DEFAULT_MAJORS = (
    "人工智能", "计科", "计数", "网合", "网安", "网络", "通信", "集成", "图灵", "香农", "智能",
    "光电", "电科", "电信", "物联", "软件", "数据", "自动化", "电子",
)  # fmt: skip
_SEPARATORS = re.compile(r"[\s,，、;；/]+")


@dataclass(frozen=True)
class ClassName:
    class_code: str  # 规范化后的班级，如 计科2501、网合25W3
    name: str  # 去掉空格后的姓名
    start: int
    end: int


def normalize_class(text: str) -> str | None:
    """“计科 2501”“网合25w3”→“计科2501”“网合25W3”；不是班级时返回 None。"""
    match = _CLASS.match(re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).strip()))
    if match is None:
        return None
    return match.group(1) + match.group(2).upper()


def majors_from(class_codes: Iterable[str]) -> tuple[str, ...]:
    """从已知班级中取专业简称，与默认列表合并，按长度从长到短排列（优先匹配长的）。"""
    found = set(DEFAULT_MAJORS)
    for code in class_codes:
        normalized = normalize_class(code)
        if normalized is not None:
            found.add(re.sub(r"\d.*$", "", normalized))
    return tuple(sorted(found, key=lambda m: (-len(m), m)))


def _pattern(majors: tuple[str, ...]) -> re.Pattern[str]:
    major = "|".join(re.escape(m) for m in majors)
    klass = rf"(?:{major})\s?{_CLASS_NUMBER}"
    # 姓名：2–4 个汉字；或“王 锦”这种两个单字之间有空格的写法；脱敏后的代号“学生0001”也算
    name = rf"学生\d{{4}}|[{CJK}]\s[{CJK}](?![{CJK}])|[{CJK}]{{2,4}}"
    # 姓名后面必须是结尾、分隔符或下一个班级，避免把下一个班级的专业简称吞进姓名
    after = rf"(?=$|[^{CJK}\dA-Za-z]|{klass})"
    return re.compile(rf"(?P<cls>{klass})\s*(?P<name>{name}){after}")


def find_class_names(text: str, majors: tuple[str, ...] = DEFAULT_MAJORS) -> list[ClassName]:
    """找出文字中所有“班级 + 姓名”。"""
    text = unicodedata.normalize("NFKC", text)
    found = []
    for m in _pattern(majors).finditer(text):
        code = normalize_class(m.group("cls"))
        assert code is not None
        found.append(ClassName(code, re.sub(r"\s", "", m.group("name")), m.start(), m.end()))
    return found


def name_list(line: str) -> list[str] | None:
    """整行都是姓名（如“邬 琦 孙晨曦 庄子文”）时返回姓名列表，否则返回 None。

    规则：按空白和标点切开后每段都是 1–4 个汉字，且至少两个姓名；相邻的两个单字合成一个姓名。
    """
    tokens = [t for t in _SEPARATORS.split(unicodedata.normalize("NFKC", line).strip()) if t]
    if not tokens or not all(re.fullmatch(rf"[{CJK}]{{1,4}}", t) for t in tokens):
        return None
    names: list[str] = []
    pending = ""
    for token in tokens:
        if len(token) == 1:
            if pending:
                names.append(pending + token)
                pending = ""
            else:
                pending = token
        else:
            if pending:
                return None  # 单字后面跟多字，无法判断怎样组合
            names.append(token)
    if pending or len(names) < 2:
        return None
    return names


def split_people(cell: str) -> list[str]:
    """拆开表格中的人名格（“张三,李四”“王 锦/2025xxxx, 杨皓宇/2025xxxx”）。"""
    people: list[str] = []
    for part in re.split(r"[,，、;；\n]+", unicodedata.normalize("NFKC", cell)):
        part = re.sub(r"/?\s*\d{6,}\s*", " ", part).strip()  # 去掉“/学号”
        listed = name_list(part)
        if listed is not None:  # “张三 李四 王五”
            people.extend(listed)
            continue
        part = re.sub(r"\s", "", part)
        if re.fullmatch(rf"[{CJK}·]{{2,6}}", part):
            people.append(part)
    return people
