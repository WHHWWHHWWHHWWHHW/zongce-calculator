"""规则版本导入与学年状态流转。"""

import copy

from fastapi.testclient import TestClient

from backend_helpers import API, CATALOG, RULES, World


def test_rule_versions(client: TestClient, world: World) -> None:
    listed = client.get(f"{API}/rules", headers=world.s1).json()
    assert [(r["rule_id"], r["version"], r["has_ability_catalog"]) for r in listed] == [
        ("ujn-v1", "1.0.0", True)
    ]
    same = client.post(
        f"{API}/rules", json={"content": RULES, "ability_catalog": CATALOG}, headers=world.admin
    )
    assert same.status_code == 201
    assert same.json()["id"] == world.rule_version_id  # 内容相同：幂等

    changed = copy.deepcopy(RULES)
    changed["title"] = "改过的标题"
    conflict = client.post(f"{API}/rules", json={"content": changed}, headers=world.admin)
    assert conflict.status_code == 409

    changed["version"] = "1.0.1"
    created = client.post(f"{API}/rules", json={"content": changed}, headers=world.admin)
    assert created.status_code == 201
    assert created.json()["has_ability_catalog"] is False

    invalid = client.post(f"{API}/rules", json={"content": {"id": "x"}}, headers=world.admin)
    assert invalid.status_code == 400
    assert "规则文件不合法" in invalid.json()["error"]["message"]
    bad_catalog = client.post(
        f"{API}/rules",
        json={"content": RULES, "ability_catalog": {"id": "x"}},
        headers=world.admin,
    )
    assert bad_catalog.json()["error"]["message"] == "能力分目录不合法"
    assert client.post(f"{API}/rules", json={"content": RULES}, headers=world.s1).status_code == 403

    content = client.get(f"{API}/rules/{world.rule_version_id}/content", headers=world.s1).json()
    assert content["rules"]["id"] == "ujn-v1"
    assert client.get(f"{API}/rules/999/content", headers=world.s1).status_code == 404


def test_years(client: TestClient, world: World) -> None:
    years = client.get(f"{API}/years", headers=world.s1).json()
    assert [(y["name"], y["status"]) for y in years] == [("2025-2026", "open")]
    body = {"name": "2026-2027", "rule_version_id": world.rule_version_id}
    created = client.post(f"{API}/years", json=body, headers=world.admin)
    assert created.status_code == 201
    year_id = created.json()["id"]
    assert client.post(f"{API}/years", json=body, headers=world.admin).status_code == 409
    unknown = {"name": "2027-2028", "rule_version_id": 999}
    assert client.post(f"{API}/years", json=unknown, headers=world.admin).status_code == 404
    bad_name = {"name": "2026", "rule_version_id": world.rule_version_id}
    assert client.post(f"{API}/years", json=bad_name, headers=world.admin).status_code == 422

    def move(status: str) -> int:
        url = f"{API}/years/{year_id}/status"
        return client.patch(url, json={"status": status}, headers=world.admin).status_code

    assert move("closed") == 400  # 未开放不能直接结束
    for status in ("open", "reviewing", "open", "reviewing", "closed"):
        assert move(status) == 200
    assert move("open") == 400
    assert (
        client.patch(
            f"{API}/years/999/status", json={"status": "open"}, headers=world.admin
        ).status_code
        == 404
    )


def test_year_catalog(client: TestClient, world: World) -> None:
    catalog = client.get(f"{API}/years/{world.year_id}/catalog", headers=world.s1).json()
    assert catalog["id"] == "xxgc-2020-ability"
    assert len(catalog["items"]) == 30
    plain = copy.deepcopy(RULES)
    plain["version"] = "2.0.0"
    version = client.post(f"{API}/rules", json={"content": plain}, headers=world.admin).json()
    year = client.post(
        f"{API}/years", json={"name": "2030-2031", "rule_version_id": version["id"]},
        headers=world.admin,
    ).json()  # fmt: skip
    missing = client.get(f"{API}/years/{year['id']}/catalog", headers=world.s1)
    assert missing.json()["error"]["message"] == "该学年的规则版本没有能力分申报目录"
