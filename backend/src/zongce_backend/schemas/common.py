"""公共类型。"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer, StringConstraints, WithJsonSchema

DecimalStr = Annotated[
    str,
    StringConstraints(pattern=r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$", max_length=40),
]
"""十进制数字符串，如 "3.6524"、"-1"、"60"。"""

NonNegativeDecimalStr = Annotated[
    str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]+)?$", max_length=40)
]


def _utc_iso(value: datetime) -> str:
    """库中时间均为 UTC（不带时区）；输出时补上时区，避免前端误当本地时间。"""
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


UtcDatetime = Annotated[
    datetime,
    PlainSerializer(_utc_iso, return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time"}),
]
"""以带时区的 ISO 8601 字符串输出的 UTC 时间，如 2026-10-13T00:00:00+00:00。"""

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


def to_decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def dec_str(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(ApiModel):
    message: str
