"""活动名单 → 表单记录 → 与申报匹配（姓名均为虚构）。"""

from decimal import Decimal

from ai_helpers import CATALOG
from zongce_ai import DeclarationRef, MatchStatus, Route, StudentRef, match
from zongce_ai.activity_lists import parse_activity_list
from zongce_ai.activity_records import class_key, records_from_entries, resolve

STUDENTS = [
    StudentRef(student_id="TEST0001", name="张三", class_name="人工智能2501"),
    StudentRef(student_id="TEST0002", name="李四", class_name="计科2501"),
    StudentRef(student_id="TEST0003", name="王五", class_name="计科2501"),
    StudentRef(student_id="TEST0004", name="王五", class_name="网安2401"),  # 重名
    StudentRef(student_id="TEST0005", name="赵六", class_name=None),
]
TEXT = """活动名称：某辩论赛
一等奖：2 分
智能 2501 张三 网合25W3 李四 计科2501 王五
二等奖：1.5 分
王五 钱七 赵六
活动名称：另一个活动
第一名：2 分
智能2501张三
工作人员：0.2 分
李四
"""


def _item(code: str) -> tuple[str, list[tuple[str, str, str]], str | None]:
    item = next(i for i in CATALOG["items"] if i["code"] == code)
    return (
        code,
        [(o["code"], o["name"], o["score"]) for o in item.get("options", [])],
        item.get("unit_score"),
    )


def test_class_key_aliases() -> None:
    assert class_key("人工智能 2501") == "智能2501"
    assert class_key("计科2501") == "计科2501"
    assert class_key("测试1班") == "测试1班"
    assert class_key(None) is None


def test_resolve_students() -> None:
    entries = parse_activity_list(TEXT).entries
    got = [(e.name, *(lambda r: (r[0].student_id if r[0] else None, r[1]))(resolve(e, STUDENTS)))
           for e in entries[:6]]  # fmt: skip
    assert got == [
        ("张三", "TEST0001", ""),  # 智能2501 = 人工智能2501
        ("李四", "TEST0002", "班级与账号不一致"),
        ("王五", "TEST0003", ""),  # 重名但班级唯一
        ("王五", None, "重名（2 人），无法确定是哪位学生"),
        ("钱七", None, "按班级和姓名找不到学生"),
        ("赵六", "TEST0005", "名单未写班级，只按姓名找到"),
    ]


def test_records_and_matching() -> None:
    entries = parse_activity_list(TEXT).entries
    culture = records_from_entries(entries, _item("campus_culture_award"), STUDENTS)
    first = culture[0]
    assert (first.student_id, first.option_code, first.value, first.group) == (
        "TEST0001", "college_1", Decimal(2), "某辩论赛",
    )  # fmt: skip
    assert first.by_name
    assert culture[1].confidence == Decimal("0.85")  # 班级不一致，交人工
    staff = culture[-1]
    assert staff.option_code is None
    assert staff.issues[-1] == "名单没有写分值或分值与该项目不符"  # 0.2 分不是校园文化活动获奖
    declarations = [
        DeclarationRef(id=1, student_id="TEST0001", option_code="college_1"),
        DeclarationRef(id=2, student_id="TEST0001", option_code="college_1"),  # 两个活动各一条
        DeclarationRef(id=3, student_id="TEST0002", option_code="college_1"),
    ]
    report = match(culture, declarations, STUDENTS)
    by_row = [(s.student_id, s.status, s.route, s.declaration_id) for s in report.suggestions]
    assert by_row[0] == ("TEST0001", MatchStatus.CONSISTENT, Route.FAST_TRACK, 1)
    assert by_row[1] == ("TEST0002", MatchStatus.CONSISTENT, Route.MANUAL, 3)  # 置信度不够
    assert by_row[3][1] is MatchStatus.UNKNOWN_STUDENT
    assert report.suggestions[3].reasons == ("重名（2 人），无法确定是哪位学生",)
    # 另一个活动，不算重复；“第一名 2 分”靠分值与默认的院级推断选项，置信度 0.85，交人工
    assert by_row[6] == ("TEST0001", MatchStatus.CONSISTENT, Route.MANUAL, 2)

    participation = records_from_entries(entries, _item("campus_participation"), STUDENTS)
    staff = participation[-1]
    assert (staff.student_id, staff.option_code, staff.unit_item) == ("TEST0002", None, True)
    report = match(
        [staff], [DeclarationRef(id=9, student_id="TEST0002", option_code=None)], STUDENTS
    )
    assert report.suggestions[0].status is MatchStatus.CONSISTENT  # 按次计分没有选项也算一致


def test_ambiguous_option_is_reported() -> None:
    from zongce_ai.activity_lists import ActivityEntry

    entry = ActivityEntry("省级某活动", "参与人员", Decimal("1.5"), "", None, "赵六", 1)
    (record,) = records_from_entries([entry], _item("campus_culture_award"), STUDENTS)
    assert record.option_code is None
    assert record.issues == ("名单未写班级，只按姓名找到", "分值对应多个选项，需人工判断")
