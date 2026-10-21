"""审计日志写入。日志只存业务数据，不记录密码等敏感信息。"""

from decimal import Decimal

from sqlalchemy.orm import Session

from .models import AuditLog, User


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def record(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: object,
    field: str | None = None,
    before: object = None,
    after: object = None,
    reason: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=None if actor is None else actor.id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        field=field,
        before=_text(before),
        after=_text(after),
        reason=reason,
    )
    db.add(entry)
    return entry
