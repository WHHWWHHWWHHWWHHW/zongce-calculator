"""公示与异议。"""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_scores import compute, import_g1

from backend_helpers import API, World
from zongce_backend.models import Publication


def test_publication_and_appeals(client: TestClient, world: World, db: Session) -> None:
    url = f"{API}/years/{world.year_id}/publications"
    empty = client.post(url, json={"class_name": "测试A班"}, headers=world.admin)
    assert empty.json()["error"]["message"] == "该班级还没有核算结果，请先核算"
    import_g1(client, world, "TEST0002")
    compute(client, world)
    created = client.post(url, json={"class_name": "测试A班"}, headers=world.admin)
    assert created.status_code == 201
    pub = created.json()
    assert pub["is_open"] is True
    assert pub["title"] == "2025-2026 学年 测试A班 综合测评成绩公示"
    assert [r["username"] for r in pub["rows"]] == ["TEST0002", "TEST0001", "TEST0003"]
    assert client.post(url, json={"class_name": "x"}, headers=world.s1).status_code == 403

    assert len(client.get(f"{API}/publications", headers=world.s1).json()) == 1
    assert client.get(f"{API}/publications", headers=world.s3).json() == []
    assert len(client.get(f"{API}/publications", params={"year_id": world.year_id},
                          headers=world.admin).json()) == 1  # fmt: skip
    assert client.get(f"{API}/publications/{pub['id']}", headers=world.s3).status_code == 404

    appeal_url = f"{API}/publications/{pub['id']}/appeals"
    appeal = client.post(appeal_url, json={"content": "我的体测成绩有误"}, headers=world.s2)
    assert appeal.status_code == 201
    assert client.post(appeal_url, json={"content": "x"}, headers=world.s3).status_code == 404
    assert client.post(appeal_url, json={"content": "x"}, headers=world.admin).status_code == 403
    mine = client.get(f"{API}/appeals", headers=world.s2).json()
    assert [(a["student_username"], a["class_name"]) for a in mine] == [("TEST0003", "测试A班")]
    assert client.get(f"{API}/appeals", headers=world.s1).json() == []
    assert len(client.get(f"{API}/appeals", params={"publication_id": pub["id"]},
                          headers=world.admin).json()) == 1  # fmt: skip

    resolve = f"{API}/appeals/{appeal.json()['id']}/resolve"
    done = client.post(
        resolve, json={"status": "accepted", "response": "已更正"}, headers=world.admin
    )
    assert (done.json()["status"], done.json()["response"]) == ("accepted", "已更正")
    twice = client.post(resolve, json={"status": "rejected", "response": "x"}, headers=world.admin)
    assert twice.status_code == 400
    assert client.post(
        f"{API}/appeals/999/resolve", json={"status": "rejected", "response": "x"},
        headers=world.admin,
    ).status_code == 404  # fmt: skip
    pending = client.post(resolve, json={"status": "pending", "response": "x"}, headers=world.admin)
    assert pending.status_code == 422

    closed = client.post(f"{API}/publications/{pub['id']}/close", headers=world.admin).json()
    assert closed["is_open"] is False
    assert (
        client.post(f"{API}/publications/{pub['id']}/close", headers=world.admin).status_code == 200
    )
    late = client.post(appeal_url, json={"content": "x"}, headers=world.s2)
    assert late.json()["error"]["message"] == "公示期已结束，不能再提出异议"

    custom = client.post(url, json={"class_name": "测试A班", "days": 1, "title": "补充公示"},
                         headers=world.admin).json()  # fmt: skip
    row = db.get(Publication, custom["id"])
    assert row is not None
    assert row.ends_at - row.starts_at == timedelta(days=1)


def test_reviewer_without_class(client: TestClient, world: World, db: Session) -> None:
    from backend_helpers import auth, make_user
    from zongce_backend.models import Role

    make_user(db, "TEST0901", Role.STUDENT, Role.CLASS_REVIEWER)
    headers = auth(client, "TEST0901")
    assert client.get(f"{API}/publications", headers=headers).json() == []
    rankings = client.get(f"{API}/years/{world.year_id}/rankings", headers=headers)
    assert rankings.status_code == 403
