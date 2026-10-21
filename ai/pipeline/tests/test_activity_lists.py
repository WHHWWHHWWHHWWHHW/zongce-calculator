"""活动获奖名单解析（写法取自真实样本的结构，姓名均为虚构）。"""

from decimal import Decimal

from ai_helpers import CATALOG
from zongce_ai.activity_lists import ActivityEntry, choose_item, parse_activity_list

TEXT = """学习部

活动名称： 新生辩论赛
第一名:2 分
智能 2501 张三 智能 2501 李四 集
成2501 王五
二等奖
1.5分
计科2501赵六 网合25w3钱七 某某某某某某
最佳辩手：1.5 分
智能 2501 张三
工作人员：0.2 分
孙八 周九 刘 一
心理协会
活动名称：健身操大赛
获奖情况： 一等奖（校第一名）
参赛人员： 3分(健脊操一等奖)
学生0001 学生0002
“光影颂华章”国庆创意征集活动获奖名单
一等奖：
学 36-424-吴十 学 23-211 郑二
"""


def _entries() -> list[ActivityEntry]:
    return list(parse_activity_list(TEXT).entries)


def test_parse_structure() -> None:
    result = parse_activity_list(TEXT)
    assert result.activities == 3
    got = [(e.activity[:4], e.level, e.points, e.class_code, e.name) for e in result.entries]
    assert got == [
        ("新生辩论", "第一名", Decimal(2), "智能2501", "张三"),
        ("新生辩论", "第一名", Decimal(2), "智能2501", "李四"),
        ("新生辩论", "第一名", Decimal(2), "集成2501", "王五"),  # 换行截断的班级接回
        ("新生辩论", "二等奖", Decimal("1.5"), "计科2501", "赵六"),
        ("新生辩论", "二等奖", Decimal("1.5"), "网合25W3", "钱七"),
        ("新生辩论", "最佳辩手", Decimal("1.5"), "智能2501", "张三"),
        ("新生辩论", "工作人员", Decimal("0.2"), None, "孙八"),
        ("新生辩论", "工作人员", Decimal("0.2"), None, "周九"),
        ("新生辩论", "工作人员", Decimal("0.2"), None, "刘一"),
        ("健身操大", "参赛人员", Decimal(3), None, "学生0001"),
        ("健身操大", "参赛人员", Decimal(3), None, "学生0002"),
        ("“光影颂", "一等奖", None, None, "吴十"),
        ("“光影颂", "一等奖", None, None, "郑二"),
    ]
    assert result.entries[9].note == "一等奖(校第一名) 健脊操一等奖"
    assert result.partial_lines == (9,)  # “某某某某某某”认不出


def _items() -> list[tuple[str, list[tuple[str, str, str]], str | None]]:
    items = []
    for code in ("campus_culture_award", "campus_participation"):
        item = next(i for i in CATALOG["items"] if i["code"] == code)
        options = [(o["code"], o["name"], o["score"]) for o in item.get("options", [])]
        items.append((code, options, item.get("unit_score")))
    return items


def test_choose_item_by_points_and_level() -> None:
    entries = _entries()
    chosen = {e.level: choose_item(e, _items()) for e in entries}
    assert chosen["第一名"] is not None
    assert (chosen["第一名"].item_code, chosen["第一名"].option_code) == (
        "campus_culture_award", "college_1",
    )  # fmt: skip
    debater = chosen["最佳辩手"]
    assert debater is not None
    assert debater.option_code == "best_debater_college"  # 1.5 分有多个选项，按“最佳辩手”区分
    staff = chosen["工作人员"]
    assert staff is not None
    assert (staff.item_code, staff.option_code) == ("campus_participation", None)
    contestant = chosen["参赛人员"]
    assert contestant is not None
    assert contestant.option_code == "university_1"  # 3 分 + “一等奖”
    assert chosen["一等奖"] is None  # 没有分值，不猜


def test_choose_item_ambiguous_and_unknown_points() -> None:
    entry = ActivityEntry("x", "二等奖", Decimal("1.5"), "", None, "张三", 1)
    choice = choose_item(entry, _items())
    assert choice is not None
    assert choice.option_code == "college_2"  # 院级二等奖与校级优秀奖都是 1.5 分，按“二等奖”区分
    vague = ActivityEntry("x", "参与人员", Decimal("1.5"), "", None, "张三", 1)
    vague_choice = choose_item(vague, _items())
    assert vague_choice is not None  # 院级 1.5 分只有二等奖；置信度低于快速通过阈值，仍需人工
    assert (vague_choice.option_code, vague_choice.confidence) == ("college_2", Decimal("0.85"))
    provincial = ActivityEntry("省级某活动", "参与人员", Decimal("1.5"), "", None, "张三", 1)
    unclear = choose_item(provincial, _items())
    assert unclear is not None
    assert (unclear.option_code, unclear.confidence) == (None, Decimal("0.4"))
    assert (
        choose_item(ActivityEntry("x", "一等奖", Decimal(99), "", None, "张三", 1), _items())
        is None
    )
    merit = choose_item(ActivityEntry("x", "优秀奖", Decimal("0.5"), "", None, "张三", 1), _items())
    assert merit is not None
    assert (merit.option_code, merit.reason) == ("college_merit", "分值唯一对应")
