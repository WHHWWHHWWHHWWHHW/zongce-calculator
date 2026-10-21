"""与申报匹配、按置信度分流。"""

from decimal import Decimal

from zongce_ai import DeclarationRef, ExtractedRecord, MatchStatus, Route, StudentRef, match

STUDENTS = [StudentRef(student_id=f"TEST0100{i}", name=f"测试学生{i}") for i in range(1, 8)]


def _record(row: int, sid: str, option: str | None, *, name: str | None = None,
            confidence: str = "0.95", issues: tuple[str, ...] = ()) -> ExtractedRecord:  # fmt: skip
    return ExtractedRecord(
        row=row, student_id=sid, name=name, option_text="", option_code=option,
        confidence=Decimal(confidence), issues=issues,
    )  # fmt: skip


def test_routes() -> None:
    records = [
        _record(2, "TEST01001", "a", name="测试学生1"),  # 一致 → 快速通过
        _record(3, "TEST01002", "b"),  # 申报为 a → 等级不符
        _record(4, "TEST01003", None, issues=("无法对应到任何选项",)),  # 等级不确定
        _record(5, "TEST01004", "a", name="别人"),  # 姓名不符
        _record(6, "TEST01005", "a", confidence="0.85"),  # 置信度低
        _record(7, "TEST01006", "a"),  # 没有申报
        _record(8, "TEST09999", "a"),  # 学号不存在
        _record(9, "TEST01001", "a"),  # 重复
        _record(10, "TEST01007", "c"),  # 第二条申报才一致
    ]
    declarations = [
        DeclarationRef(id=11, student_id="TEST01001", option_code="a"),
        DeclarationRef(id=12, student_id="TEST01002", option_code="a"),
        DeclarationRef(id=13, student_id="TEST01003", option_code="a"),
        DeclarationRef(id=14, student_id="TEST01004", option_code="a"),
        DeclarationRef(id=15, student_id="TEST01005", option_code="a"),
        DeclarationRef(id=16, student_id="TEST01007", option_code="b"),
        DeclarationRef(id=17, student_id="TEST01007", option_code="c"),
        DeclarationRef(id=18, student_id="TEST01003", option_code="b"),  # 名单中没有
    ]
    report = match(records, declarations, STUDENTS)
    got = [(s.row, s.status, s.route, s.declaration_id) for s in report.suggestions]
    assert got == [
        (2, MatchStatus.CONSISTENT, Route.FAST_TRACK, 11),
        (3, MatchStatus.OPTION_MISMATCH, Route.MANUAL, 12),
        (4, MatchStatus.UNCERTAIN, Route.MANUAL, 13),
        (5, MatchStatus.NAME_MISMATCH, Route.MANUAL, 14),
        (6, MatchStatus.CONSISTENT, Route.MANUAL, 15),
        (7, MatchStatus.NOT_DECLARED, Route.INFO, None),
        (8, MatchStatus.UNKNOWN_STUDENT, Route.MANUAL, None),
        (9, MatchStatus.DUPLICATE, Route.INFO, None),
        (10, MatchStatus.CONSISTENT, Route.FAST_TRACK, 17),
    ]
    assert report.unmatched_declarations == (16, 18)
    assert (report.count(Route.FAST_TRACK), report.count(Route.MANUAL)) == (2, 5)
    mismatch = report.suggestions[1]
    assert (mismatch.form_option, mismatch.declared_option) == ("b", "a")
    assert report.suggestions[4].reasons == ("置信度 0.85 低于阈值 0.9",)
    assert report.suggestions[2].reasons == ("无法对应到任何选项",)


def test_custom_threshold() -> None:
    record = _record(2, "TEST01001", "a", confidence="0.85")
    declaration = DeclarationRef(id=1, student_id="TEST01001", option_code="a")
    report = match([record], [declaration], STUDENTS, threshold=Decimal("0.8"))
    assert report.suggestions[0].route is Route.FAST_TRACK
