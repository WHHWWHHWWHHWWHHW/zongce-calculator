"""命令行：初始化数据库、创建管理员、导入规则、启动服务、导出 OpenAPI。"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .db import make_engine, make_session_factory
from .errors import AppError
from .models import Role, User, UserRole
from .security import hash_password
from .services.rules import create_rule_version

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _session(settings: Settings) -> Session:
    return make_session_factory(make_engine(settings.database_url))()


def init_db(settings: Settings) -> None:
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(
            parents=True, exist_ok=True
        )
    config = Config(str(ALEMBIC_INI))
    os.environ["ZONGCE_DATABASE_URL"] = settings.database_url
    command.upgrade(config, "head")


def create_admin(settings: Settings, username: str, name: str, password: str) -> None:
    with _session(settings) as db:
        if db.scalar(select(User).where(User.username == username)) is not None:
            sys.exit(f"账号 {username} 已存在")
        user = User(
            username=username, name=name, password_hash=hash_password(password),
            must_change_password=False,
        )  # fmt: skip
        user.role_rows.append(UserRole(role=Role.COLLEGE_ADMIN))
        db.add(user)
        db.commit()


def load_rules(settings: Settings, rules: Path, catalog: Path | None) -> None:
    content = json.loads(rules.read_text(encoding="utf-8"))
    ability = None if catalog is None else json.loads(catalog.read_text(encoding="utf-8"))
    with _session(settings) as db:
        try:
            version = create_rule_version(db, None, content, ability)
        except AppError as exc:
            sys.exit(exc.message)
        print(f"规则版本 #{version.id}：{version.rule_id} {version.version}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="zongce", description="综测智能核算平台")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="创建或升级数据库（alembic upgrade head）")
    admin = sub.add_parser("create-admin", help="创建学院管理员账号")
    admin.add_argument("--username", required=True)
    admin.add_argument("--name", default="学院管理员")
    load = sub.add_parser("load-rules", help="导入规则版本（及能力分目录）")
    load.add_argument("rules", type=Path)
    load.add_argument("--catalog", type=Path)
    serve = sub.add_parser("serve", help="启动 API 服务")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    export = sub.add_parser("export-openapi", help="导出 OpenAPI 文档")
    export.add_argument("output", type=Path)
    args = parser.parse_args(argv)

    if args.command == "export-openapi":
        from .main import create_app

        app = create_app(Settings(jwt_secret="x" * 32, database_url="sqlite://"))  # type: ignore[arg-type]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"
        args.output.write_text(text, encoding="utf-8")
        return

    settings = Settings()  # type: ignore[call-arg]
    if args.command == "init-db":
        init_db(settings)
    elif args.command == "create-admin":
        password = getpass.getpass("管理员密码（至少 8 位）：")
        if len(password) < 8 or password != getpass.getpass("再输入一次："):
            sys.exit("密码过短或两次输入不一致")
        create_admin(settings, args.username, args.name, password)
    elif args.command == "load-rules":
        load_rules(settings, args.rules, args.catalog)
    else:
        import uvicorn

        uvicorn.run("zongce_backend.main:create_app", factory=True, host=args.host, port=args.port)
