"""命令行：初始化数据库、创建管理员、导入规则、启动服务、导出 OpenAPI。"""

import argparse
import getpass
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import make_url, select
from sqlalchemy.orm import Session

from .config import Settings
from .db import make_engine, make_session_factory
from .errors import AppError
from .models import Role, User, UserRole
from .security import hash_password
from .services.rules import create_rule_version

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
REPO_RULES = Path(__file__).resolve().parents[3] / "rules"


@contextmanager
def _session(settings: Settings) -> Iterator[Session]:
    """命令行用的会话；用完释放连接池，避免遗留未关闭的数据库连接。"""
    engine = make_engine(settings.database_url)
    try:
        with make_session_factory(engine)() as db:
            yield db
    finally:
        engine.dispose()


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


def seed_demo(settings: Settings, args: argparse.Namespace, password: str) -> None:
    from .demo import seed_demo as run

    init_db(settings)
    with _session(settings) as db:
        try:
            summary = run(
                db, settings, password=password, rules_path=args.rules, catalog_path=args.catalog,
                classes=args.classes, students=args.students, seed=args.seed,
            )  # fmt: skip
        except AppError as exc:
            sys.exit(exc.message)
    labels = {"approved": "已通过", "rejected": "已驳回", "submitted": "待审核", "draft": "草稿"}
    counts = "，".join(f"{labels[k]} {summary.declarations.get(k, 0)}" for k in labels)
    where = make_url(settings.database_url).render_as_string(hide_password=True)
    print(f"演示库已生成（{where}）")
    print(f"- 学院管理员：{summary.admin}")
    print(f"- 班级审核员：{'、'.join(summary.reviewers)}（同时是学生）")
    print(f"- 学生：{summary.students} 人，{'、'.join(summary.classes)}，学号以 TEST 开头")
    print(f"- 学年 #{summary.year_id}：已导入学院成绩表并核算；申报：{counts}")
    print(f"- {summary.publication_class} 已发布公示，{summary.appeal_by} 提出了一条待处理的异议")
    print("- 所有演示账号使用你输入的同一个密码，不要求首次改密；只用于演示，不要放真实数据")


def _read_password(args: argparse.Namespace, prompt: str) -> str:
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
        if len(password) < 8:
            sys.exit("密码至少 8 位")
        return password
    password = getpass.getpass(f"{prompt}（至少 8 位）：")
    if len(password) < 8 or password != getpass.getpass("再输入一次："):
        sys.exit("密码过短或两次输入不一致")
    return password


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="zongce", description="综测智能核算平台")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="创建或升级数据库（alembic upgrade head）")
    admin = sub.add_parser("create-admin", help="创建学院管理员账号")
    admin.add_argument("--username", required=True)
    admin.add_argument("--name", default="学院管理员")
    admin.add_argument(
        "--password-stdin", action="store_true", help="从标准输入读取密码（用于脚本，不回显）"
    )
    load = sub.add_parser("load-rules", help="导入规则版本（及能力分目录）")
    load.add_argument("rules", type=Path)
    load.add_argument("--catalog", type=Path)
    demo = sub.add_parser(
        "seed-demo", help="生成合成演示库（账号、申报、审核、核算、公示），只能写入空库"
    )
    demo.add_argument("--classes", type=int, default=2)
    demo.add_argument("--students", type=int, default=30, help="每班人数（至少 10）")
    demo.add_argument("--seed", type=int, default=1, help="随机种子，相同种子生成相同成绩")
    demo.add_argument("--rules", type=Path, default=REPO_RULES / "ujn-v1.json")
    demo.add_argument("--catalog", type=Path, default=REPO_RULES / "ability-catalog-xxgc-2020.json")
    demo.add_argument("--password-stdin", action="store_true", help="从标准输入读取演示密码")
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
        app.state.engine.dispose()
        return

    settings = Settings()  # type: ignore[call-arg]
    if args.command == "init-db":
        init_db(settings)
    elif args.command == "create-admin":
        create_admin(settings, args.username, args.name, _read_password(args, "管理员密码"))
    elif args.command == "seed-demo":
        seed_demo(settings, args, _read_password(args, "演示账号共用的密码"))
    elif args.command == "load-rules":
        load_rules(settings, args.rules, args.catalog)
    else:
        import uvicorn

        uvicorn.run("zongce_backend.main:create_app", factory=True, host=args.host, port=args.port)
