"""底层模块与命令行。"""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import jwt
import pytest

from backend_helpers import CATALOG, RULES, xlsx
from zongce_backend import cli, tabular
from zongce_backend.config import Settings
from zongce_backend.errors import AppError, UnauthorizedError
from zongce_backend.models import DecimalText
from zongce_backend.security import (
    decode_access_token,
    generate_password,
    hash_password,
    verify_password,
)
from zongce_backend.storage import LocalFileStorage


def test_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    name = storage.save(b"data", ".pdf")
    assert storage.load(name) == b"data"
    for bad in ("../x", "a/b", "a\\b", ""):
        with pytest.raises(ValueError, match="非法"):
            storage.load(bad)
    storage.delete(name)
    storage.delete(name)  # 已删除时不报错


def test_decimal_text_rejects_float() -> None:
    column = DecimalText()
    assert column.process_bind_param(Decimal("1.50"), None) == "1.50"  # type: ignore[arg-type]
    assert column.process_bind_param(None, None) is None  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        column.process_bind_param(1.5, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        column.process_bind_param(Decimal("NaN"), None)  # type: ignore[arg-type]
    assert column.process_result_value("3.6524", None) == Decimal("3.6524")  # type: ignore[arg-type]
    assert column.process_result_value(None, None) is None  # type: ignore[arg-type]


def test_read_table_cell_types(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = tabular.read_table(
        "t.xlsx", xlsx([["学号", "值"], ["TEST1", 1e-05], [2025, 85.0], [True, None]])
    )
    assert rows[1:] == [["TEST1", "0.00001"], ["2025", "85"], ["True", ""]]
    csv_rows = tabular.read_table("t.csv", "学号,值\n\nTEST1,3.5\n".encode("gb18030"))
    assert csv_rows == [["学号", "值"], ["TEST1", "3.5"]]
    monkeypatch.setattr(tabular, "MAX_ROWS", 1)
    with pytest.raises(AppError, match="行数超过上限"):
        tabular.read_table("t.csv", b"a\nb\n")


def test_security_helpers() -> None:
    assert not verify_password(None, "anything")
    assert not verify_password("not-a-hash", "anything")
    assert verify_password(hash_password("Secret123"), "Secret123")
    password = generate_password(12)
    assert len(password) == 12
    assert not set(password) & set("0Oo1lI")
    settings = Settings(jwt_secret="s" * 40)  # type: ignore[arg-type]
    secret = settings.jwt_secret.get_secret_value()
    expired = jwt.encode(
        {"sub": "1", "ver": 0, "exp": datetime.now(UTC) - timedelta(minutes=1)}, secret, "HS256"
    )
    no_version = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) + timedelta(minutes=5)}, secret, "HS256"
    )
    for token in (expired, no_version, "garbage"):
        with pytest.raises(UnauthorizedError):
            decode_access_token(token, settings)


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "data" / "cli.sqlite3"
    monkeypatch.setenv("ZONGCE_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("ZONGCE_JWT_SECRET", "c" * 40)
    cli.main(["init-db"])
    assert db_file.exists()

    answers = iter(["Admin12345"] * 4 + ["Admin12345", "Other12345"])
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(answers))
    cli.main(["create-admin", "--username", "TESTADMIN"])
    with pytest.raises(SystemExit, match="已存在"):
        cli.main(["create-admin", "--username", "TESTADMIN"])
    with pytest.raises(SystemExit, match="不一致"):
        cli.main(["create-admin", "--username", "TESTADMIN2"])

    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps(RULES), encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps(CATALOG), encoding="utf-8")
    cli.main(["load-rules", str(rules), "--catalog", str(catalog)])
    with pytest.raises(SystemExit, match="已存在且内容不同"):
        cli.main(["load-rules", str(rules)])  # 同版本号但没有目录：内容不同，应报冲突
    output = tmp_path / "openapi.json"
    cli.main(["export-openapi", str(output)])
    assert "/api/v1/health" in json.loads(output.read_text(encoding="utf-8"))["paths"]

    calls: dict[str, object] = {}
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: calls.update(kwargs))
    cli.main(["serve", "--port", "8123"])
    assert calls == {"factory": True, "host": "127.0.0.1", "port": 8123}


def test_openapi_document_is_up_to_date(tmp_path: Path) -> None:
    """docs/api/openapi.json 是前端生成类型的依据，必须与代码一致。

    不一致时运行：uv run zongce export-openapi docs/api/openapi.json
    """
    committed = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"
    generated = tmp_path / "openapi.json"
    cli.main(["export-openapi", str(generated)])
    assert committed.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8")
