"""Alembic 迁移：从空库升级到最新，结构与 ORM 模型完全一致；可以降级回空库。

设置 ZONGCE_TEST_MYSQL_URL（如 mysql+pymysql://root:pw@127.0.0.1:3306/zongce_test）时，
同样在 MySQL 8 上验证（CI 中启用）。
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from zongce_backend.cli import ALEMBIC_INI
from zongce_backend.db import make_engine
from zongce_backend.models import Base


def _urls() -> list[str]:
    urls = ["sqlite"]
    if os.environ.get("ZONGCE_TEST_MYSQL_URL"):
        urls.append(os.environ["ZONGCE_TEST_MYSQL_URL"])
    return urls


@pytest.mark.parametrize("url", _urls(), ids=lambda u: u.split(":")[0])
def test_upgrade_matches_models_and_downgrade(url: str, tmp_path: Path) -> None:
    if url == "sqlite":
        url = f"sqlite:///{tmp_path / 'migrate.sqlite3'}"
    engine = make_engine(url)
    config = Config(str(ALEMBIC_INI))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
