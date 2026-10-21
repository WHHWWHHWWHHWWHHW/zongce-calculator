"""“班级 + 姓名”识别（只用虚构姓名）。"""

import pytest

from zongce_ai.names import (
    DEFAULT_MAJORS,
    find_class_names,
    majors_from,
    name_list,
    normalize_class,
    split_people,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("计科 2501", "计科2501"),
        ("网合25w3", "网合25W3"),
        ("人工智能2503", "人工智能2503"),
        ("计数 23H3", "计数23H3"),
        ("一等奖", None),
        ("2501", None),
    ],
)
def test_normalize_class(text: str, expected: str | None) -> None:
    assert normalize_class(text) == expected


def test_majors_from_known_classes() -> None:
    majors = majors_from(["测绘2401", "计科 2501", "不是班级"])
    assert "测绘" in majors
    assert majors.index("人工智能") < majors.index("智能")  # 长的优先
    assert set(DEFAULT_MAJORS) <= set(majors)


def test_find_class_names_in_dense_text() -> None:
    text = "计科 2501 张三 网合25w3李四 计科2502王 五 智能2501赵六网安2401钱小七"
    got = [(c.class_code, c.name) for c in find_class_names(text)]
    assert got == [
        ("计科2501", "张三"),
        ("网合25W3", "李四"),
        ("计科2502", "王五"),
        ("智能2501", "赵六"),
        ("网安2401", "钱小七"),
    ]


def test_pseudonyms_count_as_names() -> None:
    got = [(c.class_code, c.name) for c in find_class_names("计科2501学生0012 网合 25W3 学生0345")]
    assert got == [("计科2501", "学生0012"), ("网合25W3", "学生0345")]


def test_unknown_major_needs_majors_list() -> None:
    text = "测绘2401 孙八"
    assert find_class_names(text) == []
    found = find_class_names(text, majors_from(["测绘2401"]))
    assert [(c.class_code, c.name, c.start, c.end) for c in found] == [("测绘2401", "孙八", 0, 9)]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("刘 一 陈小明 周九", ["刘一", "陈小明", "周九"]),
        ("张三、李四", ["张三", "李四"]),
        ("一等奖", None),  # 只有一个词
        ("参赛人员： 3 分", None),
        ("刘 陈小明", None),  # 单字后面跟多字
        ("张三 李 四 王", None),  # 末尾落单
        ("", None),
    ],
)
def test_name_list(line: str, expected: list[str] | None) -> None:
    assert name_list(line) == expected


def test_split_people() -> None:
    assert split_people("张三,李四") == ["张三", "李四"]
    assert split_people("王 五/202500000001, 赵六/20250000002") == ["王五", "赵六"]
    assert split_people("陈小明 周九 吴十") == ["陈小明", "周九", "吴十"]
    assert split_people("无") == []
