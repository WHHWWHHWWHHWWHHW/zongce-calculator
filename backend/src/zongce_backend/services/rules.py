"""规则版本：上传、校验、取用（引擎 RuleSet 与能力分目录按版本缓存）。"""

import hashlib
import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from zongce_engine import RuleError, RuleSet

from .. import audit
from ..catalog import AbilityCatalog
from ..errors import AppError, ConflictError, NotFoundError
from ..models import RuleVersion, User

_RULESETS: dict[tuple[int, str], RuleSet] = {}
_CATALOGS: dict[tuple[int, str], AbilityCatalog] = {}


def _canonical(content: dict[str, Any], catalog: dict[str, Any] | None) -> bytes:
    payload = {"rules": content, "ability_catalog": catalog}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def create_rule_version(
    db: Session, actor: User | None, content: dict[str, Any], catalog: dict[str, Any] | None
) -> RuleVersion:
    try:
        ruleset = RuleSet.from_dict(content)
    except RuleError as exc:
        raise AppError(f"规则文件不合法：{exc}") from exc
    if catalog is not None:
        try:
            AbilityCatalog.model_validate(catalog)
        except ValidationError as exc:
            raise AppError("能力分目录不合法", details=exc.errors(include_url=False)) from exc
    sha = hashlib.sha256(_canonical(content, catalog)).hexdigest()
    existing = db.scalar(
        select(RuleVersion).where(
            RuleVersion.rule_id == ruleset.id, RuleVersion.version == ruleset.version
        )
    )
    if existing is not None:
        if existing.sha256 == sha:
            return existing
        raise ConflictError(f"规则 {ruleset.id} {ruleset.version} 已存在且内容不同，请提升版本号")
    version = RuleVersion(
        rule_id=ruleset.id,
        version=ruleset.version,
        title=ruleset.title,
        content=content,
        ability_catalog=catalog,
        sha256=sha,
        created_by=None if actor is None else actor.id,
    )
    db.add(version)
    db.flush()
    audit.record(
        db, actor=actor, action="rules.created", entity_type="rule_version", entity_id=version.id,
        after=f"{ruleset.id} {ruleset.version} sha256={sha}",
    )  # fmt: skip
    db.commit()
    return version


def get_rule_version(db: Session, version_id: int) -> RuleVersion:
    version = db.get(RuleVersion, version_id)
    if version is None:
        raise NotFoundError("规则版本不存在")
    return version


def ruleset_of(version: RuleVersion) -> RuleSet:
    key = (version.id, version.sha256)
    if key not in _RULESETS:
        _RULESETS[key] = RuleSet.from_dict(version.content)
    return _RULESETS[key]


def catalog_of(version: RuleVersion) -> AbilityCatalog:
    if version.ability_catalog is None:
        raise AppError("该学年的规则版本没有能力分申报目录")
    key = (version.id, version.sha256)
    if key not in _CATALOGS:
        _CATALOGS[key] = AbilityCatalog.model_validate(version.ability_catalog)
    return _CATALOGS[key]
