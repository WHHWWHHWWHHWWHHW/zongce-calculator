"""规则版本与学年。"""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from ..catalog import AbilityCatalog
from ..deps import AdminUser, CurrentUser, DbSession
from ..models import RuleVersion
from ..schemas.years import (
    RuleVersionCreate,
    RuleVersionOut,
    YearCreate,
    YearOut,
    YearStatusUpdate,
)
from ..services import rules as rule_service
from ..services import years as service

router = APIRouter(tags=["规则与学年"])


def _rule_out(version: RuleVersion) -> RuleVersionOut:
    return RuleVersionOut(
        id=version.id,
        rule_id=version.rule_id,
        version=version.version,
        title=version.title,
        sha256=version.sha256,
        has_ability_catalog=version.ability_catalog is not None,
        created_at=version.created_at,
    )


@router.get("/rules", response_model=list[RuleVersionOut], summary="规则版本列表")
def list_rules(_: CurrentUser, db: DbSession) -> list[RuleVersionOut]:
    return [_rule_out(v) for v in db.scalars(select(RuleVersion).order_by(RuleVersion.id))]


@router.post("/rules", response_model=RuleVersionOut, status_code=201, summary="导入规则版本")
def create_rules(body: RuleVersionCreate, admin: AdminUser, db: DbSession) -> RuleVersionOut:
    return _rule_out(
        rule_service.create_rule_version(db, admin, body.content, body.ability_catalog)
    )


@router.get("/rules/{version_id}/content", summary="规则版本原文（规则 JSON 与能力分目录）")
def rule_content(version_id: int, _: CurrentUser, db: DbSession) -> dict[str, Any]:
    version = rule_service.get_rule_version(db, version_id)
    return {"rules": version.content, "ability_catalog": version.ability_catalog}


@router.get("/years", response_model=list[YearOut], summary="学年列表")
def list_years(_: CurrentUser, db: DbSession) -> list[YearOut]:
    return [YearOut.model_validate(y) for y in service.list_years(db)]


@router.post("/years", response_model=YearOut, status_code=201, summary="新建学年")
def create_year(body: YearCreate, admin: AdminUser, db: DbSession) -> YearOut:
    return YearOut.model_validate(service.create_year(db, admin, body.name, body.rule_version_id))


@router.patch("/years/{year_id}/status", response_model=YearOut, summary="学年状态流转")
def set_status(year_id: int, body: YearStatusUpdate, admin: AdminUser, db: DbSession) -> YearOut:
    return YearOut.model_validate(service.set_status(db, admin, year_id, body.status))


@router.get(
    "/years/{year_id}/catalog", response_model=AbilityCatalog, summary="该学年的能力分申报目录"
)
def year_catalog(year_id: int, _: CurrentUser, db: DbSession) -> AbilityCatalog:
    year = service.get_year(db, year_id)
    return rule_service.catalog_of(year.rule_version)
