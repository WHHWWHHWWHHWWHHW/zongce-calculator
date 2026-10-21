"""合成演示数据：生成的文件能完整导入、核算、排名（也作为一次端到端集成测试）。"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from backend_helpers import API, World, upload, xlsx

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gen_fake_data.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_fake_data", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_data_imports_and_scores(client: TestClient, world: World) -> None:
    gen = _load()
    users = gen.users_rows(2, 12)
    assert all(row[0].startswith("TEST") for row in users[1:])
    created = client.post(
        f"{API}/users/import", files=upload("users.xlsx", xlsx(users)), headers=world.admin
    ).json()
    assert (len(created["created"]), created["errors"]) == (24, [])

    college = gen.college_rows(2, 12, seed=7)
    assert college == gen.college_rows(2, 12, seed=7)  # 同一种子结果相同
    imported = client.post(
        f"{API}/years/{world.year_id}/college-data/import",
        files=upload("college.xlsx", xlsx(college)),
        headers=world.admin,
    ).json()
    assert imported["errors"] == []
    assert imported["changed"] == 24 * 9

    computed = client.post(
        f"{API}/years/{world.year_id}/scores/compute", json={}, headers=world.admin
    ).json()
    assert computed["computed"] == 24 + 4  # 合成学生 + 预置的 4 个学生账号
    rows = client.get(
        f"{API}/years/{world.year_id}/rankings", params={"class_name": "测试1班"},
        headers=world.admin,
    ).json()  # fmt: skip
    assert len(rows) == 12
    assert rows[0]["rank"] == 1
    assert all(r["moral_total"] is not None for r in rows)


def test_main_writes_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gen = _load()
    argv = ["gen_fake_data.py", "--out", str(tmp_path), "--classes", "1", "--students", "3"]
    monkeypatch.setattr("sys.argv", argv)
    gen.main()
    assert (tmp_path / "users.xlsx").exists()
    assert (tmp_path / "college.xlsx").exists()
