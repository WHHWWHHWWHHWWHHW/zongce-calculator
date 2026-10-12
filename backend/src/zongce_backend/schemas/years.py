"""规则版本与学年。"""

from typing import Annotated, Any

from pydantic import StringConstraints

from ..models import YearStatus
from .common import ApiModel, UtcDatetime


class RuleVersionCreate(ApiModel):
    content: dict[str, Any]
    ability_catalog: dict[str, Any] | None = None


class RuleVersionOut(ApiModel):
    id: int
    rule_id: str
    version: str
    title: str
    sha256: str
    has_ability_catalog: bool
    created_at: UtcDatetime


class YearCreate(ApiModel):
    name: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{4}$")]
    rule_version_id: int


class YearStatusUpdate(ApiModel):
    status: YearStatus


class YearOut(ApiModel):
    id: int
    name: str
    rule_version_id: int
    status: YearStatus
    created_at: UtcDatetime
