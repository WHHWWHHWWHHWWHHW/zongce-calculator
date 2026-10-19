"""演示库：一条命令生成账号、申报、审核、核算、公示（只含合成数据）。"""

import io
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend_helpers import API, REPO_ROOT, auth
from zongce_backend import cli
from zongce_backend.config import Settings
from zongce_backend.demo import ADMIN_USERNAME, seed_demo
from zongce_backend.errors import AppError
from zongce_backend.models import (
    Appeal,
    AuditLog,
    Declaration,
    DeclarationStatus,
    EvidenceFile,
    ReviewRecord,
    ScoreResult,
    User,
)

RULES = REPO_ROOT / "rules" / "ujn-v1.json"
CATALOG = REPO_ROOT / "rules" / "ability-catalog-xxgc-2020.json"
DEMO_PASSWORD = "Demo12345"


def _seed(db: Session, settings: Settings, **kwargs: int) -> None:
    seed_demo(
        db, settings, password=DEMO_PASSWORD, rules_path=RULES, catalog_path=CATALOG,
        **{"classes": 2, "students": 10, **kwargs},
    )  # fmt: skip


def _ability(db: Session, username: str) -> Decimal:
    result = db.scalar(
        select(ScoreResult)
        .join(User, ScoreResult.student_id == User.id)
        .where(User.username == username)
    )
    assert result is not None
    return result.ability_total


def test_seed_demo_builds_a_complete_year(
    client: TestClient, db: Session, settings: Settings
) -> None:
    _seed(db, settings)
    statuses = dict(
        db.execute(select(Declaration.status, func.count()).group_by(Declaration.status)).all()
    )
    assert statuses == {
        DeclarationStatus.APPROVED: 10,  # 每班 4 条 + 审核员本人 1 条（由管理员审核）
        DeclarationStatus.REJECTED: 2,
        DeclarationStatus.SUBMITTED: 4,
        DeclarationStatus.DRAFT: 2,
    }
    assert db.scalar(select(func.count()).select_from(ReviewRecord)) == 12
    assert db.scalar(select(func.count()).select_from(EvidenceFile)) == 16
    assert db.scalar(select(func.count()).select_from(ScoreResult)) == 20
    assert (db.scalar(select(func.count()).select_from(AuditLog)) or 0) > 0
    assert db.scalar(select(func.count()).select_from(Appeal)) == 1
    assert all(u.username.startswith("TEST") or u.username == ADMIN_USERNAME
               for u in db.scalars(select(User)))  # fmt: skip

    # 能力分来自通过的申报：校级优秀学生 3；团队项目 20 ×（3−1+1）/ 6 = 10；改分后 3；驳回 0
    assert _ability(db, "TEST01002") == Decimal("3")
    assert _ability(db, "TEST01003") == Decimal("10")
    assert _ability(db, "TEST01005") == Decimal("3")
    assert _ability(db, "TEST01006") == Decimal("0")

    admin = auth(client, ADMIN_USERNAME, DEMO_PASSWORD)  # 演示账号不要求首次改密
    me = client.get(f"{API}/auth/me", headers=admin).json()
    assert me["must_change_password"] is False
    years = client.get(f"{API}/years", headers=admin).json()
    rows = client.get(
        f"{API}/years/{years[0]['id']}/rankings", params={"class_name": "测试1班"},
        headers=admin,
    ).json()  # fmt: skip
    assert [r["rank"] for r in rows][:1] == [1]
    reviewer = auth(client, "TEST01001", DEMO_PASSWORD)
    pending = client.get(
        f"{API}/declarations", params={"status": "submitted"}, headers=reviewer
    ).json()
    assert len(pending) == 2  # 本班待审核


def test_seed_demo_refuses_non_empty_database_and_bad_arguments(
    db: Session, settings: Settings
) -> None:
    with pytest.raises(AppError, match="每班至少 10 人"):
        _seed(db, settings, students=9)
    with pytest.raises(AppError, match="至少 8 位"):
        seed_demo(db, settings, password="short", rules_path=RULES, catalog_path=CATALOG)
    _seed(db, settings)
    with pytest.raises(AppError, match="只能写入空库"):
        _seed(db, settings)


def test_seed_demo_rejects_non_object_rules(
    db: Session, settings: Settings, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    with pytest.raises(AppError, match="不是 JSON 对象"):
        seed_demo(db, settings, password=DEMO_PASSWORD, rules_path=bad, catalog_path=CATALOG)


def test_cli_seed_demo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ZONGCE_DATABASE_URL", f"sqlite:///{tmp_path / 'demo.sqlite3'}")
    monkeypatch.setenv("ZONGCE_JWT_SECRET", "d" * 40)
    monkeypatch.setenv("ZONGCE_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{DEMO_PASSWORD}\n"))
    cli.main(["seed-demo", "--password-stdin", "--classes", "1", "--students", "10"])
    out = capsys.readouterr().out
    assert "演示库已生成" in out
    assert "TEST01001" in out
    assert DEMO_PASSWORD not in out  # 不回显密码
    assert any((tmp_path / "uploads").rglob("*.pdf"))

    monkeypatch.setattr("sys.stdin", io.StringIO(f"{DEMO_PASSWORD}\n"))
    with pytest.raises(SystemExit, match="只能写入空库"):
        cli.main(["seed-demo", "--password-stdin"])
