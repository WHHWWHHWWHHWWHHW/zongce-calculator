"""后端测试公共夹具：每个测试一个独立的 SQLite 库。"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend_helpers import CATALOG, RULES, World, auth, make_user
from zongce_backend.config import Settings
from zongce_backend.main import create_app
from zongce_backend.models import AcademicYear, Base, Role, RuleVersion, YearStatus
from zongce_backend.services.rules import create_rule_version


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        jwt_secret="t" * 40,  # type: ignore[arg-type]
        database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=64 * 1024,
        max_files_per_declaration=3,
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    session: Session = app.state.session_factory()
    yield session
    session.close()


@pytest.fixture
def world(client: TestClient, db: Session) -> World:
    make_user(db, "TESTADMIN", Role.COLLEGE_ADMIN)
    make_user(db, "TEST0001", Role.STUDENT, Role.CLASS_REVIEWER, class_name="测试A班")
    make_user(db, "TEST0002", Role.STUDENT, class_name="测试A班")
    make_user(db, "TEST0003", Role.STUDENT, class_name="测试A班")
    make_user(db, "TEST0101", Role.STUDENT, class_name="测试B班")
    version: RuleVersion = create_rule_version(db, None, RULES, CATALOG)
    year = AcademicYear(name="2025-2026", rule_version_id=version.id, status=YearStatus.OPEN)
    db.add(year)
    db.commit()
    return World(
        admin=auth(client, "TESTADMIN"),
        reviewer=auth(client, "TEST0001"),
        s1=auth(client, "TEST0002"),
        s2=auth(client, "TEST0003"),
        s3=auth(client, "TEST0101"),
        year_id=year.id,
        rule_version_id=version.id,
    )
