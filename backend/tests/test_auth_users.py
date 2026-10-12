"""认证、强制改密、账号导入与管理。"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend_helpers import API, PASSWORD, World, auth, make_user, upload, xlsx
from zongce_backend.models import AuditLog, Role


def test_health_and_openapi(client: TestClient) -> None:
    assert client.get(f"{API}/health").json()["status"] == "ok"
    spec = client.get(f"{API}/openapi.json").json()
    assert "/api/v1/score/preview" in spec["paths"]


def test_login_failures_use_unified_error(client: TestClient, db: Session) -> None:
    make_user(db, "TEST9001", Role.STUDENT)
    for username, password in (("TEST9001", "wrong-pass"), ("NOBODY", PASSWORD)):
        response = client.post(
            f"{API}/auth/login", json={"username": username, "password": password}
        )
        assert response.status_code == 401
        assert response.json()["error"] == {
            "code": "unauthorized",
            "message": "账号或密码错误",
            "details": None,
        }


def test_inactive_user_cannot_login(client: TestClient, db: Session) -> None:
    user = make_user(db, "TEST9002", Role.STUDENT)
    user.is_active = False
    db.commit()
    response = client.post(f"{API}/auth/login", json={"username": "TEST9002", "password": PASSWORD})
    assert response.status_code == 401


def test_missing_or_bad_token(client: TestClient) -> None:
    assert client.get(f"{API}/years").json()["error"]["code"] == "unauthorized"
    bad = client.get(f"{API}/years", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401
    assert bad.headers["www-authenticate"] == "Bearer"


def test_validation_error_structure(client: TestClient) -> None:
    response = client.post(f"{API}/auth/login", json={"username": "x"})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"][0]["loc"] == ["body", "password"]


def test_unknown_route_uses_unified_error(client: TestClient) -> None:
    response = client.get(f"{API}/no-such-route")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_404"


def test_import_then_forced_password_change(client: TestClient, world: World) -> None:
    data = xlsx(
        [
            ["学号", "姓名", "班级", "角色"],
            ["TEST1001", "测试甲", "测试C班", ""],
            ["TEST1002", "测试乙", "测试C班", "学生、班级审核员"],
            ["bad name", "测试丙", "测试C班", ""],
            ["TEST1001", "测试甲", "测试C班", ""],
            ["TEST1003", "", "测试C班", ""],
            ["TEST1004", "测试丁", "测试C班", "校长"],
            ["TEST0002", "测试TEST0002", "测试A班", "学生"],
            ["TEST0003", "新名字", "测试A班", "student"],
        ]
    )
    response = client.post(
        f"{API}/users/import", files=upload("users.xlsx", data), headers=world.admin
    )
    assert response.status_code == 200, response.text
    result = response.json()
    created = {c["username"]: c["initial_password"] for c in result["created"]}
    assert set(created) == {"TEST1001", "TEST1002"}
    assert (result["updated"], result["unchanged"]) == (1, 1)
    assert [e["row"] for e in result["errors"]] == [4, 5, 6, 7]

    headers = auth(client, "TEST1002", created["TEST1002"])
    me = client.get(f"{API}/auth/me", headers=headers).json()
    assert me["must_change_password"] is True
    assert me["roles"] == ["class_reviewer", "student"]
    blocked = client.get(f"{API}/years", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"

    def change(old: str, new: str) -> int:
        body = {"old_password": old, "new_password": new}
        return client.post(f"{API}/auth/change-password", json=body, headers=headers).status_code

    assert change("wrong-old-pass", "NewPassw0rd") == 400
    assert change(created["TEST1002"], created["TEST1002"]) == 400
    assert change(created["TEST1002"], "TEST1002") == 400
    assert change(created["TEST1002"], "NewPassw0rd") == 200
    # 改密码后旧令牌失效
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401
    fresh = auth(client, "TEST1002", "NewPassw0rd")
    assert client.get(f"{API}/years", headers=fresh).status_code == 200


def test_import_csv_and_header_errors(client: TestClient, world: World) -> None:
    csv_data = "学号,姓名,班级\nTEST2001,测试戊,测试D班\n".encode("gb18030")
    response = client.post(
        f"{API}/users/import", files=upload("u.csv", csv_data), headers=world.admin
    )
    assert [c["username"] for c in response.json()["created"]] == ["TEST2001"]
    missing = client.post(
        f"{API}/users/import",
        files=upload("u.csv", "班级\n测试D班\n".encode()),
        headers=world.admin,
    )
    assert missing.status_code == 400
    assert "学号" in missing.json()["error"]["message"]
    empty = client.post(f"{API}/users/import", files=upload("u.csv", b""), headers=world.admin)
    assert empty.json()["error"]["message"] == "表格为空"
    wrong = client.post(f"{API}/users/import", files=upload("u.txt", b"x"), headers=world.admin)
    assert wrong.json()["error"]["message"] == "只支持 .xlsx 或 .csv 文件"
    broken = client.post(f"{API}/users/import", files=upload("u.xlsx", b"x"), headers=world.admin)
    assert "无法读取 Excel" in broken.json()["error"]["message"]
    too_big = client.post(
        f"{API}/users/import", files=upload("u.csv", b"a" * (64 * 1024 + 1)), headers=world.admin
    )
    assert "大小上限" in too_big.json()["error"]["message"]


def test_non_admin_cannot_manage_users(client: TestClient, world: World) -> None:
    assert client.get(f"{API}/users", headers=world.s1).status_code == 403
    assert client.get(f"{API}/users", headers=world.reviewer).status_code == 403


def test_list_update_reset(client: TestClient, world: World, db: Session) -> None:
    users = client.get(f"{API}/users", params={"class_name": "测试A班"}, headers=world.admin).json()
    assert [u["username"] for u in users] == ["TEST0001", "TEST0002", "TEST0003"]
    reviewers = client.get(f"{API}/users", params={"role": "class_reviewer"}, headers=world.admin)
    assert [u["username"] for u in reviewers.json()] == ["TEST0001"]
    target = users[2]["id"]

    updated = client.patch(
        f"{API}/users/{target}",
        json={"name": "测试改名", "class_name": "测试B班", "roles": ["student", "class_reviewer"]},
        headers=world.admin,
    ).json()
    assert (updated["name"], updated["class_name"]) == ("测试改名", "测试B班")
    assert updated["roles"] == ["class_reviewer", "student"]

    cleared = client.patch(f"{API}/users/{target}", json={"class_name": ""}, headers=world.admin)
    assert cleared.json()["class_name"] is None

    reset = client.post(f"{API}/users/{target}/reset-password", headers=world.admin).json()
    headers = auth(client, "TEST0003", reset["initial_password"])
    assert client.get(f"{API}/auth/me", headers=headers).json()["must_change_password"] is True

    deactivated = client.patch(
        f"{API}/users/{target}", json={"is_active": False}, headers=world.admin
    )
    assert deactivated.json()["is_active"] is False
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401

    me = client.get(f"{API}/auth/me", headers=world.admin).json()
    for body in ({"is_active": False}, {"roles": ["student"]}):
        response = client.patch(f"{API}/users/{me['id']}", json=body, headers=world.admin)
        assert response.status_code == 409
    assert client.patch(f"{API}/users/99999", json={}, headers=world.admin).status_code == 404

    actions = {a.action for a in db.scalars(select(AuditLog))}
    assert {"user.updated", "user.password_reset"} <= actions
