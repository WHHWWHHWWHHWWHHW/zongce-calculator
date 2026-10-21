"""ORM 基础：声明基类、命名约定、精确十进制列类型、时间工具。"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, Dialect, Enum, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """当前 UTC 时间（不带时区信息；库中统一存 UTC）。"""
    return datetime.now(UTC).replace(tzinfo=None)


class DecimalText(TypeDecorator[Decimal]):
    """以字符串存储 Decimal，保证在 SQLite 与 MySQL 上都精确无损（禁止 float）。"""

    impl = String(40)
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if not isinstance(value, Decimal) or not value.is_finite():
            raise TypeError(f"DecimalText 只接受有限的 Decimal，实际为 {value!r}")
        return format(value, "f")

    def process_result_value(self, value: str | None, dialect: Dialect) -> Decimal | None:
        return None if value is None else Decimal(value)


def enum_column(enum: type[StrEnum]) -> Enum:
    """以 VARCHAR + CHECK 约束存储枚举值（不用数据库原生 ENUM，便于迁移）。"""
    return Enum(
        enum,
        native_enum=False,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
        create_constraint=True,
        name=enum.__name__.lower(),
    )


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}  # noqa: RUF012


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, server_default=func.now()
    )
