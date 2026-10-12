"""能力分申报、证明材料与审核。"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend_helpers import API, World
from zongce_backend.models import AcademicYear, AuditLog, YearStatus

PDF = b"%PDF-1.4\n%synthetic test file\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def declare(client: TestClient, world: World, headers: dict[str, str], **fields: Any) -> Any:
    body = {"year_id": world.year_id, "title": "测试申报", **fields}
    return client.post(f"{API}/declarations", json=body, headers=headers)


@pytest.mark.parametrize(
    ("fields", "suggested"),
    [
        ({"catalog_code": "honor_national", "option_code": "national"}, "20.0000"),
        (
            {"catalog_code": "competition", "option_code": "c1_national_1", "team_size": 3,
             "team_position": 2},
            "13.3333",
        ),
        ({"catalog_code": "cadre", "option_code": "minister", "concurrent_rank": 2}, "1.0000"),
        ({"catalog_code": "public_service_extra", "quantity": 3}, "1.5000"),
        ({"catalog_code": "outstanding_deeds", "claimed_score": "3"}, None),
    ],
)  # fmt: skip
def test_create_suggested_score(
    client: TestClient, world: World, fields: dict[str, Any], suggested: str | None
) -> None:
    response = declare(client, world, world.s1, **fields)
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["suggested_score"], body["status"]) == (suggested, "draft")
    assert body["student_username"] == "TEST0002"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"catalog_code": "nope"}, "未知的申报项目"),
        ({"catalog_code": "honor_national"}, "请为“国家级荣誉称号”选择"),
        ({"catalog_code": "honor_other", "option_code": "x"}, "没有级别/奖项可选"),
        ({"catalog_code": "public_service_extra"}, "请填写“公益劳动附加分"),
        ({"catalog_code": "honor_college", "option_code": "college", "quantity": 2},
         "不按数量计分"),
        (
            {"catalog_code": "competition", "option_code": "college_1", "team_size": 3},
            "需同时填写",
        ),
        (
            {"catalog_code": "competition", "option_code": "college_1", "team_size": 2,
             "team_position": 3},
            "位次须在",
        ),
        ({"catalog_code": "honor_college", "option_code": "college", "team_size": 2},
         "不是多人项目"),
        ({"catalog_code": "cadre", "option_code": "member", "concurrent_rank": 5}, "排序须在"),
        ({"catalog_code": "honor_college", "option_code": "college", "concurrent_rank": 1},
         "不涉及"),
    ],
)  # fmt: skip
def test_create_validation(
    client: TestClient, world: World, fields: dict[str, Any], message: str
) -> None:
    response = declare(client, world, world.s1, **fields)
    assert response.status_code == 400
    assert message in response.json()["error"]["message"]


def test_only_students_in_open_year(client: TestClient, world: World, db: Session) -> None:
    fields = {"catalog_code": "honor_college", "option_code": "college"}
    assert declare(client, world, world.admin, **fields).status_code == 403
    year = db.get(AcademicYear, world.year_id)
    assert year is not None
    year.status = YearStatus.REVIEWING
    db.commit()
    response = declare(client, world, world.s1, **fields)
    assert response.json()["error"]["message"] == "该学年当前不在申报期"


def test_lifecycle_update_submit_withdraw(client: TestClient, world: World) -> None:
    d = declare(
        client, world, world.s1, catalog_code="honor_university", option_code="other"
    ).json()
    url = f"{API}/declarations/{d['id']}"
    updated = client.patch(url, json={"option_code": "top_ten", "title": "改后"}, headers=world.s1)
    assert (updated.json()["suggested_score"], updated.json()["title"]) == ("5.0000", "改后")
    assert (
        client.patch(url, json={"title": "x"}, headers=world.s2).status_code == 404
    )  # 同班也看不到
    assert client.patch(url, json={"title": "x"}, headers=world.reviewer).status_code == 403
    claimed = client.patch(url, json={"claimed_score": "4.5"}, headers=world.s1).json()
    assert claimed["claimed_score"] == "4.5"
    submitted = client.post(f"{url}/submit", headers=world.s1).json()
    assert submitted["status"] == "submitted"
    assert client.post(f"{url}/submit", headers=world.s1).status_code == 400
    assert client.patch(url, json={"title": "x"}, headers=world.s1).status_code == 400
    assert client.post(f"{url}/withdraw", headers=world.s1).json()["status"] == "withdrawn"
    assert client.post(f"{url}/withdraw", headers=world.s1).status_code == 400
    assert client.get(f"{API}/declarations/99999", headers=world.s1).status_code == 404


def test_list_scopes(client: TestClient, world: World) -> None:
    fields = {"catalog_code": "honor_college", "option_code": "college"}
    for headers in (world.s1, world.s2, world.s3, world.reviewer):
        assert declare(client, world, headers, **fields).status_code == 201

    def owners(headers: dict[str, str], **params: Any) -> list[str]:
        response = client.get(f"{API}/declarations", params=params, headers=headers)
        return sorted(d["student_username"] for d in response.json())

    assert owners(world.s1) == ["TEST0002"]
    assert owners(world.reviewer) == ["TEST0001", "TEST0002", "TEST0003"]
    assert owners(world.reviewer, mine=True) == ["TEST0001"]
    assert len(owners(world.admin)) == 4
    assert owners(world.admin, class_name="测试B班") == ["TEST0101"]
    assert owners(world.admin, year_id=world.year_id, status="draft") == owners(world.admin)
    assert owners(world.admin, status="approved") == []


def test_reviewer_without_class_sees_nothing(client: TestClient, world: World, db: Session) -> None:
    from backend_helpers import auth, make_user
    from zongce_backend.models import Role

    make_user(db, "TEST0900", Role.CLASS_REVIEWER)
    assert client.get(f"{API}/declarations", headers=auth(client, "TEST0900")).json() == []


def test_evidence(client: TestClient, world: World) -> None:
    d = declare(client, world, world.s1, catalog_code="honor_college", option_code="college").json()
    url = f"{API}/declarations/{d['id']}/evidence"
    ids = []
    for name, data, content_type in (
        ("证书.pdf", PDF, "application/pdf"),
        ("a.png", PNG, "image/png"),
        ("b.jpg", JPEG, "image/jpeg"),
    ):
        response = client.post(url, files={"file": (name, data, "text/plain")}, headers=world.s1)
        assert response.status_code == 201, response.text
        assert response.json()["content_type"] == content_type
        ids.append(response.json()["id"])
    too_many = client.post(url, files={"file": ("c.pdf", PDF)}, headers=world.s1)
    assert "最多上传 3 个" in too_many.json()["error"]["message"]

    download = client.get(f"{API}/evidence/{ids[0]}", headers=world.reviewer)
    assert download.content == PDF
    assert "filename*=UTF-8''%E8%AF%81%E4%B9%A6.pdf" in download.headers["content-disposition"]
    assert download.headers["x-content-type-options"] == "nosniff"
    assert detail_time_is_utc(client, world, d["id"])
    assert client.get(f"{API}/evidence/{ids[0]}", headers=world.s3).status_code == 404
    assert client.get(f"{API}/evidence/99999", headers=world.s1).status_code == 404

    assert client.delete(f"{API}/evidence/{ids[2]}", headers=world.s2).status_code == 404
    assert client.delete(f"{API}/evidence/{ids[2]}", headers=world.s1).status_code == 204
    detail = client.get(f"{API}/declarations/{d['id']}", headers=world.s1).json()
    assert len(detail["evidence"]) == 2

    exe = client.post(url, files={"file": ("x.pdf", b"MZ\x90\x00")}, headers=world.s1)
    assert exe.json()["error"]["message"] == "只支持 PDF、PNG、JPEG 格式的证明材料"
    empty = client.post(url, files={"file": ("x.pdf", b"")}, headers=world.s1)
    assert empty.json()["error"]["message"] == "文件为空"
    big = client.post(url, files={"file": ("x.pdf", PDF + b"0" * 70000)}, headers=world.s1)
    assert "大小上限" in big.json()["error"]["message"]

    client.post(f"{API}/declarations/{d['id']}/submit", headers=world.s1)
    locked = client.post(url, files={"file": ("x.pdf", PDF)}, headers=world.s1)
    assert locked.json()["error"]["message"] == "只有草稿或被驳回的申报可以上传材料"
    assert client.delete(f"{API}/evidence/{ids[0]}", headers=world.s1).status_code == 400


def detail_time_is_utc(client: TestClient, world: World, declaration_id: int) -> bool:
    detail = client.get(f"{API}/declarations/{declaration_id}", headers=world.s1).json()
    return all(e["created_at"].endswith("+00:00") for e in detail["evidence"])


def _submitted(client: TestClient, world: World, headers: dict[str, str], **fields: Any) -> int:
    d = declare(client, world, headers, **fields).json()
    client.post(f"{API}/declarations/{d['id']}/submit", headers=headers)
    return int(d["id"])


def review(client: TestClient, headers: dict[str, str], declaration_id: int, **body: Any) -> Any:
    return client.post(f"{API}/declarations/{declaration_id}/review", json=body, headers=headers)


def test_review_flow_and_audit(client: TestClient, world: World, db: Session) -> None:
    did = _submitted(
        client, world, world.s1, catalog_code="honor_university", option_code="top_ten"
    )
    approved = review(client, world.reviewer, did, action="approve", reason="材料齐全")
    assert (approved.json()["status"], approved.json()["approved_score"]) == ("approved", "5.0000")
    again = review(client, world.reviewer, did, action="adjust", score="3", reason="x")
    assert again.status_code == 403  # 已通过的只有管理员能改
    adjusted = review(client, world.admin, did, action="adjust", score="3", reason="与另一项重复")
    assert adjusted.json()["approved_score"] == "3"
    history = client.get(f"{API}/declarations/{did}/reviews", headers=world.s1).json()
    assert [(h["action"], h["score_before"], h["score_after"]) for h in history] == [
        ("approve", None, "5.0000"),
        ("adjust", "5.0000", "3"),
    ]
    logs = db.scalars(select(AuditLog).where(AuditLog.entity_type == "declaration")).all()
    assert [(log.before, log.after, log.reason) for log in logs] == [
        (None, "5.0000", "材料齐全"),
        ("5.0000", "3", "与另一项重复"),
    ]
    audit = client.get(
        f"{API}/audit-logs", params={"entity_type": "declaration"}, headers=world.admin
    )
    assert len(audit.json()) == 2
    filtered = client.get(
        f"{API}/audit-logs", params={"action": "declaration.adjust", "entity_id": str(did)},
        headers=world.admin,
    )  # fmt: skip
    assert len(filtered.json()) == 1
    assert client.get(f"{API}/audit-logs", headers=world.reviewer).status_code == 403


def test_review_rules(client: TestClient, world: World, db: Session) -> None:
    did = _submitted(client, world, world.s1, catalog_code="outstanding_deeds")
    reason = {"reason": "测试"}
    assert review(client, world.reviewer, did, action="approve", **reason).status_code == 400
    assert (
        review(client, world.reviewer, did, action="approve", score="2", **reason).status_code
        == 400
    )
    assert review(client, world.reviewer, did, action="adjust", **reason).status_code == 400
    out_of_range = review(client, world.reviewer, did, action="adjust", score="6", **reason)
    assert "1–5" in out_of_range.json()["error"]["message"]
    assert (
        review(client, world.reviewer, did, action="reject", score="1", **reason).status_code == 400
    )
    blank = review(client, world.reviewer, did, action="reject", reason="  ")
    assert blank.status_code == 422  # 理由必填
    rejected = review(client, world.reviewer, did, action="reject", **reason).json()
    assert (rejected["status"], rejected["approved_score"]) == ("rejected", None)
    assert review(client, world.reviewer, did, action="reject", **reason).status_code == 400
    # 被驳回后可以修改并重新提交
    url = f"{API}/declarations/{did}"
    assert (
        client.patch(url, json={"claimed_score": "2"}, headers=world.s1).json()["status"] == "draft"
    )
    client.post(f"{url}/submit", headers=world.s1)
    claimed = review(client, world.reviewer, did, action="approve", **reason).json()
    assert claimed["approved_score"] == "2"

    own = _submitted(
        client, world, world.reviewer, catalog_code="honor_college", option_code="college"
    )
    assert review(client, world.reviewer, own, action="approve", **reason).status_code == 403
    other_class = _submitted(
        client, world, world.s3, catalog_code="honor_college", option_code="college"
    )
    assert (
        review(client, world.reviewer, other_class, action="approve", **reason).status_code == 404
    )
    assert review(client, world.s2, did, action="approve", **reason).status_code == 404

    year = db.get(AcademicYear, world.year_id)
    assert year is not None
    year.status = YearStatus.CLOSED
    db.commit()
    closed = review(client, world.admin, did, action="adjust", score="1", **reason)
    assert closed.json()["error"]["message"] == "该学年已结束，不能再修改"
