"""审计日志查询（学院管理员）。"""

from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..deps import AdminUser, DbSession
from ..models import AuditLog
from ..schemas.common import ApiModel

router = APIRouter(tags=["审计日志"])


class AuditLogOut(ApiModel):
    id: int
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: str
    field: str | None
    before: str | None
    after: str | None
    reason: str | None
    created_at: datetime


@router.get("/audit-logs", response_model=list[AuditLogOut], summary="审计日志")
def list_logs(
    _: AdminUser,
    db: DbSession,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogOut]:
    query = select(AuditLog).order_by(AuditLog.id.desc())
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    rows = db.scalars(query.limit(limit).offset(offset))
    return [AuditLogOut.model_validate(r) for r in rows]
