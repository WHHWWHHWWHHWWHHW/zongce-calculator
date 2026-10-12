"""后端测试辅助：造数据、登录、构造上传文件（只含合成数据，CLAUDE.md §11）。"""

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from zongce_backend.models import Role, User, UserRole
from zongce_backend.security import hash_password

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES = json.loads((REPO_ROOT / "rules" / "ujn-v1.json").read_text(encoding="utf-8"))
CATALOG = json.loads(
    (REPO_ROOT / "rules" / "ability-catalog-xxgc-2020.json").read_text(encoding="utf-8")
)
PASSWORD = "Passw0rd!"
API = "/api/v1"


def make_user(
    db: Session,
    username: str,
    *roles: Role,
    class_name: str | None = None,
    must_change: bool = False,
) -> User:
    user = User(
        username=username,
        name=f"测试{username}",
        class_name=class_name,
        password_hash=hash_password(PASSWORD),
        must_change_password=must_change,
    )
    user.role_rows = [UserRole(role=r) for r in roles]
    db.add(user)
    db.commit()
    return user


def auth(client: TestClient, username: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@dataclass
class World:
    """预置数据：管理员、A 班审核员（也是学生）、A 班两名学生、B 班一名学生、
    规则版本、开放中的学年。"""

    admin: dict[str, str]
    reviewer: dict[str, str]
    s1: dict[str, str]
    s2: dict[str, str]
    s3: dict[str, str]
    year_id: int
    rule_version_id: int


def xlsx(rows: list[list[Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def upload(name: str, data: bytes) -> dict[str, tuple[str, bytes]]:
    return {"file": (name, data)}


PDF = b"%PDF-1.4\n%synthetic test file\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
