"""公共类型。"""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

DecimalStr = Annotated[
    str,
    StringConstraints(pattern=r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$", max_length=40),
]
"""十进制数字符串，如 "3.6524"、"-1"、"60"。"""

NonNegativeDecimalStr = Annotated[
    str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]+)?$", max_length=40)
]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


def to_decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def dec_str(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(ApiModel):
    message: str
