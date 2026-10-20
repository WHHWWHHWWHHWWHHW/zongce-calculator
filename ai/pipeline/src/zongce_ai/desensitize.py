"""真实表单脱敏（CLAUDE.md §11）：姓名换成“学生0001”“教师001”，学号等长换成随机数字。

同一个人在所有文件里换成同一个代号，换完后的数据仍然可以用来评测“按班级 + 姓名匹配”。
对照表只保存在本机的 real_data/ 目录，不提交、不外发。

只处理已经读成文字的数据（表格的行、页面文字）；读文件的部分在 ai/eval/desensitize.py。
"""

import random
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from .names import CJK, find_class_names, majors_from, name_list, normalize_class, split_people

STUDENT_HEADERS = re.compile(r"姓名|获奖学生|获奖人|负责人|成员|参赛|队员|作者|学生名单|人员")
TEACHER_HEADERS = re.compile(r"教师|老师")
LABELLED = re.compile(
    rf"(?P<label>指导教师|指导老师|负责人|联系人|参赛人员|队员|成员|获奖人|作者|姓名)\s*[:：]\s*"
    rf"(?P<names>[{CJK} \t,，、/]+)"  # 不跨行
)
DIGITS = re.compile(r"\d{8,}")


@dataclass
class Table:
    rows: list[list[str]]


@dataclass
class Document:
    """一个源文件读出的内容：若干表格 + 全文文字。"""

    name: str
    tables: list[Table] = field(default_factory=list)
    text: str = ""


@dataclass
class People:
    students: set[str] = field(default_factory=set)
    teachers: set[str] = field(default_factory=set)
    ids: set[str] = field(default_factory=set)
    class_codes: set[str] = field(default_factory=set)


def _header(row: Sequence[str]) -> dict[int, str] | None:
    """表头行 → {列号: "student" | "teacher" | "class"}；不是表头时返回 None。

    表头的每一格都不长（不超过 20 个字），不含长数字，也不含班级；这样不会把数据行当成表头。
    """
    if any(
        len(c.strip()) > 20
        or DIGITS.search(c)
        or normalize_class(c)
        or re.fullmatch(r"\d+(\.\d+)?", c.strip())  # 序号、分数等数字只出现在数据行
        for c in row
    ):
        return None
    roles: dict[int, str] = {}
    for col, cell in enumerate(row):
        label = re.sub(r"\s", "", cell)
        if len(label) > 12:  # 表头关键词所在的格都很短
            continue
        if TEACHER_HEADERS.search(label):
            roles[col] = "teacher"
        elif STUDENT_HEADERS.search(label):
            roles[col] = "student"
        elif label == "班级":
            roles[col] = "class"
    return roles or None


def _collect_text(text: str, people: People, majors: tuple[str, ...]) -> None:
    for found in find_class_names(text, majors):
        people.students.add(found.name)
        people.class_codes.add(found.class_code)
    for line in text.splitlines():
        listed = name_list(line)
        if listed is not None:
            people.students.update(listed)
    for m in LABELLED.finditer(text):
        target = (
            people.teachers
            if "教" in m.group("label") or "老师" in m.group("label")
            else (people.students)
        )
        target.update(split_people(m.group("names")))
    people.ids.update(DIGITS.findall(text))


def collect(documents: Sequence[Document], known_classes: Iterable[str] = ()) -> People:
    """找出所有需要替换的姓名和学号。先看表格（按表头判断哪一列是人名），再看文字。"""
    people = People()
    people.class_codes.update(known_classes)
    for doc in documents:
        for table in doc.tables:
            roles: dict[int, str] | None = None
            for row in table.rows:
                header = _header(row)
                if header is not None:
                    roles = header
                    continue
                for col, cell in enumerate(row):
                    role = (roles or {}).get(col)
                    if role == "class":
                        people.class_codes.add(cell.strip())
                    elif role is not None:
                        names = split_people(cell)
                        (people.teachers if role == "teacher" else people.students).update(names)
                    people.ids.update(DIGITS.findall(cell))
    # 以上来自表头明确的人名列，一定是姓名；下面从文字中按写法推断的，要过滤掉明显不是姓名的词
    majors = majors_from(people.class_codes)
    guessed = People()
    for doc in documents:
        for table in doc.tables:
            for row in table.rows:
                for cell in row:
                    _collect_text(cell, guessed, majors)
        _collect_text(doc.text, guessed, majors)
    titles = [doc.name for doc in documents]
    people.students |= {n for n in guessed.students if _plausible(n, titles)}
    people.teachers |= {n for n in guessed.teachers if _plausible(n, titles)}
    people.ids |= guessed.ids
    people.class_codes |= guessed.class_codes
    people.teachers -= people.students
    return people


# 表单里常见、但不会是姓名的词与字（按写法推断的姓名含有它们时不算姓名）
_NOT_NAMES = frozenset(
    {"宿舍", "班级", "姓名", "名单", "学号", "序号", "备注", "合计", "总计", "小计", "优秀", "获奖",
     "名次", "参赛", "活动", "无"}
)  # fmt: skip
_NOT_NAME_CHARS = re.compile("[奖级部院赛队组室舍楼届期表]")


def _plausible(name: str, titles: Sequence[str]) -> bool:
    return (
        name not in _NOT_NAMES
        and not _NOT_NAME_CHARS.search(name)
        and not any(name in title for title in titles)  # 出现在文件名里的是普通词
    )


class Desensitizer:
    """按收集到的人名和学号做替换；同一个人始终换成同一个代号。"""

    def __init__(self, people: People, seed: bytes) -> None:
        rng = random.Random(seed)
        students = sorted(people.students)
        teachers = sorted(people.teachers)
        rng.shuffle(students)
        rng.shuffle(teachers)
        self.mapping: dict[str, str] = {n: f"学生{i:04d}" for i, n in enumerate(students, 1)}
        self.mapping.update({n: f"教师{i:03d}" for i, n in enumerate(teachers, 1)})
        self.id_mapping: dict[str, str] = {}
        used = set(people.ids)
        for real in sorted(people.ids):
            while True:
                fake = str(rng.randint(1, 9)) + "".join(
                    str(rng.randint(0, 9)) for _ in range(len(real) - 1)
                )
                if fake not in used:  # pragma: no branch - 撞号概率极低，撞了就重抽
                    break
            used.add(fake)
            self.id_mapping[real] = fake
        # 姓名的每个字之间允许有空格（“王 锦”）；长的先换，避免短名替换掉长名的一部分
        names = sorted(self.mapping, key=lambda n: (-len(n), n))
        self._names = (
            re.compile("|".join(r"\s?".join(map(re.escape, n)) for n in names)) if names else None
        )

    def scrub(self, text: str) -> str:
        text = DIGITS.sub(lambda m: self.id_mapping.get(m.group(), "0" * len(m.group())), text)
        if self._names is None:
            return text
        return self._names.sub(lambda m: self.mapping[re.sub(r"\s", "", m.group())], text)

    def leaks(self, text: str) -> int:
        """脱敏后的文字里还剩多少处原始姓名或学号（应为 0）。"""
        count = sum(1 for m in DIGITS.finditer(text) if m.group() in self.id_mapping)
        if self._names is not None:
            count += len(self._names.findall(text))
        return count


PSEUDONYM = re.compile(r"学生\d{4}|教师\d{3}")
_CLASS_CODE = re.compile(rf"[{CJK}]{{2,6}}\s?\d{{2}}[A-Za-z]?\d{{1,2}}")


def column_residue(tables: Sequence[Sequence[Sequence[str]]]) -> int:
    """脱敏后的表格里，人名列中仍有汉字（不是代号）的格数（应为 0）。"""
    count = 0
    for rows in tables:
        roles: dict[int, str] | None = None
        for row in rows:
            header = _header(row)
            if header is not None:
                roles = header
                continue
            for col, cell in enumerate(row):
                if (roles or {}).get(col) in ("student", "teacher"):
                    rest = _CLASS_CODE.sub("", PSEUDONYM.sub("", cell))  # 班级不是人名
                    if re.search(rf"[{CJK}]{{2,}}", rest) and rest.strip() not in _NON_NAMES:
                        count += 1
    return count


_NON_NAMES = frozenset({"无", "暂无", "待定", "空"})


def suspicious(text: str, majors: tuple[str, ...]) -> int:
    """脱敏后仍像“班级 + 姓名”或整行姓名的地方（可能是没收集到的姓名，需要检查）。"""
    count = len(find_class_names(text, majors))
    count += sum(1 for line in text.splitlines() if name_list(line) is not None)
    return count
