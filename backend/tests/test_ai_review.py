"""AI 辅助审核：名单比对只给建议；批量确认逐条走审核流程并留痕（只含合成数据）。"""

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
