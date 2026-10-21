"""Alembic 迁移环境。

数据库地址优先级：调用方传入的连接（测试用）> ZONGCE_DATABASE_URL > 本机 SQLite 默认值。
"""

import os
from typing import Any

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy import Connection

from zongce_backend.db import make_engine
from zongce_backend.models import Base, DecimalText

DEFAULT_URL = "sqlite:///./data/zongce.sqlite3"
target_metadata = Base.metadata


def _render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | bool:
    """迁移脚本中把 DecimalText 写成普通 VARCHAR(40)，避免迁移依赖应用代码。"""
    if type_ == "type" and isinstance(obj, DecimalText):
        return "sa.String(length=40)"
    return False


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=os.environ.get("ZONGCE_DATABASE_URL", DEFAULT_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _configure(connection)
        return
    engine = make_engine(os.environ.get("ZONGCE_DATABASE_URL", DEFAULT_URL))
    with engine.connect() as conn:
        _configure(conn)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
