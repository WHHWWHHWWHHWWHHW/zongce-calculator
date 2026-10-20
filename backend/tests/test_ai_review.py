"""AI 辅助审核：名单比对只给建议；批量确认逐条走审核流程并留痕（只含合成数据）。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend_helpers import API, PASSWORD, World, auth, make_user, upload
from zongce_backend.models import AuditLog, Declaration, DeclarationStatus, Role

LIST = (
    "序号,学号,姓名,获奖级别,获奖等级\n"
    "1,TEST0002,测试TEST0002,省级,一等奖\n"  # 与申报一致 → 可快速通过
    "2,TEST0003,测试TEST0003,省级,一等奖\n"  # 申报为二等奖 → 人工复核
    "3,TEST0101,测试TEST0101,国家级,一等奖\n"  # B 班
    "4,TEST9999,不存在,省级,三等奖\n"  # 学号不存在
    "5,,,,\n"
)


def _declare(client: TestClient, headers: dict[str, str], year_id: int, option: str) -> int:
    body = {"year_id": year_id, "catalog_code": "competition", "option_code": option,
            "title": "某学科竞赛"}  # fmt: skip
    created = client.post(f"{API}/declarations", json=body, headers=headers).json()
    client.post(f"{API}/declarations/{created['id']}/submit", headers=headers)
    return int(created["id"])


def _match(client: TestClient, world: World, headers: dict[str, str], **extra: str) -> dict:  # type: ignore[type-arg]
    data = {"catalog_code": "competition", "context": "一类赛事", **extra}
    response = client.post(
        f"{API}/years/{world.year_id}/ai/award-match",
        data=data, files=upload("名单.csv", LIST.encode()), headers=headers,
    )  # fmt: skip
    assert response.status_code == 200, response.text
    result: dict = response.json()  # type: ignore[type-arg]
    return result


def test_match_and_confirm(client: TestClient, world: World, db: Session) -> None:
    d1 = _declare(client, world.s1, world.year_id, "c1_provincial_1")
    d2 = _declare(client, world.s2, world.year_id, "c1_provincial_2")
    d3 = _declare(client, world.s3, world.year_id, "c1_national_1")

    mine = _match(client, world, world.reviewer)  # A 班审核员
    assert mine["catalog_name"] == "专业类或学术性竞赛"
    assert mine["skipped_rows"] == [6]
    assert mine["out_of_scope_rows"] == 1  # B 班学生不显示
    got = {s["student_username"]: (s["status"], s["route"], s["declaration_id"])
           for s in mine["suggestions"]}  # fmt: skip
    assert got == {
        "TEST0002": ("consistent", "fast_track", d1),
        "TEST0003": ("option_mismatch", "manual", d2),
        "TEST9999": ("unknown_student", "manual", None),
    }
    assert mine["counts"] == {"fast_track": 1, "manual": 2, "info": 0}
    first = mine["suggestions"][0]
    assert first["form_option_name"].startswith("一类赛事 省级 一等奖")
    assert first["declaration_title"] == "某学科竞赛"
    assert first["confidence"] == "0.95"
    mismatch = mine["suggestions"][1]
    assert mismatch["declared_option_name"].startswith("一类赛事 省级 二等奖")

    everyone = _match(client, world, world.admin)
    assert everyone["out_of_scope_rows"] == 0
    assert everyone["counts"]["fast_track"] == 2
    # 比对只给建议：申报状态不变
    assert db.get(Declaration, d1).status == DeclarationStatus.SUBMITTED  # type: ignore[union-attr]

    confirm = client.post(
        f"{API}/years/{world.year_id}/ai/fast-track",
        json={"declaration_ids": [d1, d3, d1, 9999], "source": "竞赛获奖名单.csv"},
        headers=world.reviewer,
    ).json()
    assert confirm["approved"] == 1
    assert [(i["declaration_id"], i["ok"]) for i in confirm["items"]] == [
        (d1, True), (d3, False), (9999, False),
    ]  # fmt: skip
    db.expire_all()
    assert db.get(Declaration, d1).status == DeclarationStatus.APPROVED  # type: ignore[union-attr]
    log = db.scalars(select(AuditLog).where(AuditLog.action == "declaration.approve")).one()
    assert log.reason is not None
    assert "竞赛获奖名单.csv" in log.reason
    assert "审核员批量确认" in log.reason

    again = client.post(
        f"{API}/years/{world.year_id}/ai/fast-track",
        json={"declaration_ids": [d1], "source": "x"}, headers=world.admin,
    ).json()  # fmt: skip
    assert again["items"][0]["message"] == "只能确认待审核的申报"


def test_confirm_rejects_other_year(client: TestClient, world: World, db: Session) -> None:
    d1 = _declare(client, world.s1, world.year_id, "c1_provincial_1")
    other = client.post(
        f"{API}/years", json={"name": "2026-2027", "rule_version_id": world.rule_version_id},
        headers=world.admin,
    ).json()  # fmt: skip
    result = client.post(
        f"{API}/years/{other['id']}/ai/fast-track",
        json={"declaration_ids": [d1], "source": "x"}, headers=world.admin,
    ).json()  # fmt: skip
    assert result["items"][0]["message"] == "申报不属于该学年"


def test_status_and_errors(client: TestClient, world: World, db: Session) -> None:
    status = client.get(f"{API}/ai/status", headers=world.s1).json()
    assert status == {"provider": "none", "table_matching": True, "image_recognition": False,
                      "fast_track_threshold": "0.9"}  # fmt: skip
    url = f"{API}/years/{world.year_id}/ai/award-match"

    def post(
        name: str, data: bytes, code: str = "competition", headers: dict[str, str] | None = None
    ) -> tuple[int, str]:
        response = client.post(
            url, data={"catalog_code": code}, files=upload(name, data),
            headers=headers or world.admin,
        )  # fmt: skip
        return response.status_code, response.json().get("error", {}).get("message", "")

    status_code, message = post("名单.png", b"\x89PNG\r\n")
    assert status_code == 400
    assert "AI_PROVIDER=none" in message
    assert post("名单.csv", b"name\n")[1] == "表头缺少“学号”列"
    assert post("名单.csv", LIST.encode(), code="outstanding_deeds")[1].endswith("无法按名单比对")
    assert post("名单.csv", LIST.encode(), code="nope")[0] == 400
    assert post("名单.csv", LIST.encode(), headers=world.s1)[0] == 403

    make_user(db, "TESTREV2", Role.CLASS_REVIEWER)  # 没有班级的审核员看不到任何学生
    lonely = auth(client, "TESTREV2", PASSWORD)
    result = _match(client, world, lonely)
    assert {s["status"] for s in result["suggestions"]} == {"unknown_student"}
    assert result["out_of_scope_rows"] == 3


ACTIVITY_LIST = """学习部
活动名称：新生辩论赛
一等奖：2 分
计科 2501 张三 网安2401 王五
二等奖：1.5 分
李四 赵六
网安2401 孙八
"""


def _people(db: Session) -> None:
    """名单比对按姓名找人，需要真实写法的姓名（虚构）与“专业 + 年级班号”的班级。"""
    for username, name, klass, roles in (
        ("TEST7100", "钱审核", "计科2501", (Role.STUDENT, Role.CLASS_REVIEWER)),
        ("TEST7101", "张三", "计科2501", (Role.STUDENT,)),
        ("TEST7102", "李四", "计科2501", (Role.STUDENT,)),
        ("TEST7103", "王五", "网安2401", (Role.STUDENT,)),
    ):
        user = make_user(db, username, *roles, class_name=klass)
        user.name = name
    db.commit()


def _activity_match(
    client: TestClient, world: World, headers: dict[str, str], name: str, data: bytes
) -> dict:  # type: ignore[type-arg]
    response = client.post(
        f"{API}/years/{world.year_id}/ai/award-match",
        data={"catalog_code": "campus_culture_award"},
        files=upload(name, data),
        headers=headers,
    )
    assert response.status_code == 200, response.text
    result: dict = response.json()  # type: ignore[type-arg]
    return result


def test_activity_list_by_class_and_name(client: TestClient, world: World, db: Session) -> None:
    _people(db)
    student = auth(client, "TEST7101")
    body = {"year_id": world.year_id, "catalog_code": "campus_culture_award",
            "option_code": "college_1", "title": "新生辩论赛一等奖"}  # fmt: skip
    created = client.post(f"{API}/declarations", json=body, headers=student).json()
    client.post(f"{API}/declarations/{created['id']}/submit", headers=student)

    reviewer = auth(client, "TEST7100")
    mine = _activity_match(client, world, reviewer, "学习部.txt", ACTIVITY_LIST.encode())
    got = {s["student_username"]: (s["status"], s["route"]) for s in mine["suggestions"]}
    assert got == {
        "TEST7101": ("consistent", "fast_track"),  # 班级 + 姓名，分值 2 → 院级一等奖
        "TEST7102": ("not_declared", "info"),  # 只按姓名找到
        "赵六": ("unknown_student", "manual"),
    }
    assert mine["out_of_scope_rows"] == 2  # 网安2401 的学生（含没找到的）对计科2501 的审核员不可见
    unknown = next(s for s in mine["suggestions"] if s["student_username"] == "赵六")
    assert unknown["reasons"] == ["按班级和姓名找不到学生"]
    first = next(s for s in mine["suggestions"] if s["student_username"] == "TEST7101")
    assert (first["student_name"], first["declaration_id"]) == ("张三", created["id"])

    admin = _activity_match(
        client, world, world.admin, "学习部.txt", ACTIVITY_LIST.encode("gb18030")
    )
    assert "TEST7103" in {s["student_username"] for s in admin["suggestions"]}


def test_activity_list_pdf(
    client: TestClient, world: World, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _people(db)

    class Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class Pdf:
        def __init__(self) -> None:
            self.pages = [Page(ACTIVITY_LIST), Page("")]

        def __enter__(self) -> "Pdf":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    import pdfplumber

    monkeypatch.setattr(pdfplumber, "open", lambda _f: Pdf())
    result = _activity_match(client, world, world.admin, "学习部.pdf", b"%PDF-1.4")
    assert len(result["suggestions"]) == 5


def test_activity_list_errors(client: TestClient, world: World) -> None:
    url = f"{API}/years/{world.year_id}/ai/award-match"

    def post(name: str, data: bytes, code: str = "campus_culture_award") -> tuple[int, str]:
        response = client.post(
            url, data={"catalog_code": code}, files=upload(name, data), headers=world.admin
        )
        return response.status_code, response.json().get("error", {}).get("message", "")

    blank = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    status, message = post("扫描件.pdf", blank)
    assert status == 400
    assert "没有文字层" in message
    assert "AI_PROVIDER=none" in message
    assert post("坏文件.pdf", b"not a pdf")[1] == "无法读取 PDF 文件"
    assert post("空.txt", "一些文字".encode())[1].startswith("没有识别出名单")
    assert post("名单.txt", ACTIVITY_LIST.encode(), code="outstanding_deeds")[1].endswith(
        "无法按名单比对"
    )
    participation = post("名单.txt", ACTIVITY_LIST.encode(), code="campus_participation")
    assert participation[0] == 200
