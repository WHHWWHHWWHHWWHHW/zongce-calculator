"""核算：从学院成绩数据与已通过的申报组装引擎输入，调用 zongce_engine 计分。"""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from zongce_engine import (
    MoralValue,
    PeerRatings,
    ScoreInput,
    calculate,
    parse_rating_text,
)
from zongce_engine import ScoreResult as EngineResult

from .. import audit
from ..catalog import aggregate
from ..errors import ForbiddenError, NotFoundError
from ..models import (
    AcademicYear,
    CollegeRecord,
    Declaration,
    DeclarationStatus,
    Role,
    RuleVersion,
    ScoreField,
    ScoreResult,
    User,
    UserRole,
    utcnow,
)
from ..schemas.scores import MoralInput, PreviewRequest
from .rules import catalog_of, get_rule_version, ruleset_of
from .years import get_year, require_not_closed


def _dec(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _moral(value: MoralInput | None) -> MoralValue:
    if value is None:
        return None
    if value.ratings is not None:
        return PeerRatings(tuple(Decimal(v) for v in value.ratings))
    if value.ratings_text is not None:
        return PeerRatings(tuple(parse_rating_text(value.ratings_text)))
    return _dec(value.score)


def preview(db: Session, req: PreviewRequest) -> EngineResult:
    if req.rule_version_id is not None:
        version = get_rule_version(db, req.rule_version_id)
    else:
        latest = db.scalar(select(RuleVersion).order_by(RuleVersion.id.desc()))
        if latest is None:
            raise NotFoundError("尚未导入任何规则版本")
        version = latest
    score_input = ScoreInput(
        gpa=_dec(req.gpa),
        quality_mode=req.quality_mode,
        quality_direct=_dec(req.quality_direct),
        political=_moral(req.political),
        morality=_moral(req.morality),
        discipline=_moral(req.discipline),
        integrity=_moral(req.integrity),
        second_classroom=_dec(req.second_classroom),
        public_service=_dec(req.public_service),
        fitness_test=_dec(req.fitness_test),
        dorm_check=_dec(req.dorm_check),
        ability=_dec(req.ability),
    )
    return calculate(score_input, ruleset_of(version))


def _input_text(record: CollegeRecord) -> list[str] | str | None:
    if record.ratings is not None:
        return list(record.ratings)
    return None if record.value is None else format(record.value, "f")


def _record_value(record: CollegeRecord) -> MoralValue:
    if record.ratings is not None:
        return PeerRatings(tuple(Decimal(v) for v in record.ratings))
    return record.value


def _ability(db: Session, year: AcademicYear, student: User) -> tuple[Decimal, dict[str, Any]]:
    declarations = list(
        db.scalars(
            select(Declaration)
            .where(
                Declaration.year_id == year.id,
                Declaration.student_id == student.id,
                Declaration.status == DeclarationStatus.APPROVED,
            )
            .order_by(Declaration.id)
        )
    )
    scored = [(d.catalog_code, d.approved_score or Decimal(0)) for d in declarations]
    if year.rule_version.ability_catalog is None:
        total = sum((s for _, s in scored), Decimal(0))
        groups: list[dict[str, str | bool]] = []
    else:
        total, groups = aggregate(catalog_of(year.rule_version), scored)
    detail = {
        "total": format(total, "f"),
        "declarations": [
            {"id": d.id, "catalog_code": d.catalog_code, "score": format(s, "f")}
            for d, (_, s) in zip(declarations, scored, strict=True)
        ],
        "groups": groups,
    }
    return total, detail


def _student_input(
    db: Session, year: AcademicYear, student: User
) -> tuple[ScoreInput, Decimal, dict[str, Any]]:
    records = {
        r.field: r
        for r in db.scalars(
            select(CollegeRecord).where(
                CollegeRecord.year_id == year.id, CollegeRecord.student_id == student.id
            )
        )
    }
    ability, ability_detail = _ability(db, year, student)

    def value(field: ScoreField) -> Decimal | None:
        record = records.get(field)
        return None if record is None else record.value

    def moral(field: ScoreField) -> MoralValue:
        record = records.get(field)
        return None if record is None else _record_value(record)

    quality_direct = value(ScoreField.QUALITY_DIRECT)
    score_input = ScoreInput(
        gpa=value(ScoreField.GPA),
        quality_mode="direct" if quality_direct is not None else "detail",
        quality_direct=quality_direct,
        political=moral(ScoreField.POLITICAL),
        morality=moral(ScoreField.MORALITY),
        discipline=moral(ScoreField.DISCIPLINE),
        integrity=moral(ScoreField.INTEGRITY),
        second_classroom=value(ScoreField.SECOND_CLASSROOM),
        public_service=value(ScoreField.PUBLIC_SERVICE),
        fitness_test=value(ScoreField.FITNESS_TEST),
        dorm_check=value(ScoreField.DORM_CHECK),
        ability=ability,
    )
    inputs = {f.value: _input_text(r) for f, r in records.items()}
    return score_input, ability, {"inputs": inputs, "ability": ability_detail}


def _items(result: EngineResult) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": i.rule_id,
            "score": format(i.score, "f"),
            "raw": None if i.raw is None else format(i.raw, "f"),
            "capped": i.capped,
            "floored": i.floored,
            "peer_count": i.peer_count,
            "peer_trimmed_per_side": i.peer_trimmed_per_side,
        }
        for i in result.items
    ]


def compute_year(
    db: Session, actor: User, year_id: int, class_name: str | None, reason: str
) -> tuple[int, int]:
    """核算一个学年（可限定班级）全部在籍学生，返回 (核算人数, 综测成绩变化人数)。"""
    year = get_year(db, year_id)
    require_not_closed(year)
    ruleset = ruleset_of(year.rule_version)
    query = (
        select(User)
        .where(User.is_active.is_(True), User.role_rows.any(UserRole.role == Role.STUDENT))
        .order_by(User.username)
    )
    if class_name:
        query = query.where(User.class_name == class_name)
    computed = changed = 0
    for student in db.scalars(query):
        score_input, ability, detail = _student_input(db, year, student)
        result = calculate(score_input, ruleset)
        detail.update(rules={"id": ruleset.id, "version": ruleset.version}, items=_items(result))
        stored = db.scalar(
            select(ScoreResult).where(
                ScoreResult.year_id == year.id, ScoreResult.student_id == student.id
            )
        )
        before = None if stored is None else stored.final_score
        if stored is None:
            stored = ScoreResult(year_id=year.id, student_id=student.id)
            db.add(stored)
        stored.rule_version_id = year.rule_version_id
        stored.final_score = result.final_score
        stored.gpa = result.gpa
        stored.quality_total = result.quality_total
        stored.moral_total = result.moral_total
        stored.competence_total = result.competence_total
        stored.ability_total = ability
        stored.detail = detail
        stored.computed_at = utcnow()
        stored.computed_by = actor.id
        computed += 1
        if before != result.final_score:
            changed += 1
            audit.record(
                db, actor=actor, action="score.computed", entity_type="student",
                entity_id=student.id, field=f"{year.name}.final_score", before=before,
                after=result.final_score, reason=reason,
            )  # fmt: skip
    db.commit()
    return computed, changed


def stored_scores(
    db: Session, user: User, year_id: int, class_name: str | None
) -> list[ScoreResult]:
    get_year(db, year_id)
    query = (
        select(ScoreResult)
        .join(User, User.id == ScoreResult.student_id)
        .where(ScoreResult.year_id == year_id)
        .order_by(User.class_name, User.username)
    )
    if user.has_role(Role.COLLEGE_ADMIN):
        if class_name:
            query = query.where(User.class_name == class_name)
    elif user.has_role(Role.CLASS_REVIEWER) and user.class_name is not None:
        query = query.where(User.class_name == user.class_name)
    else:
        query = query.where(User.id == user.id)
    return list(db.scalars(query).unique())


def require_class_access(user: User, class_name: str | None) -> None:
    if user.has_role(Role.COLLEGE_ADMIN):
        return
    if not user.has_role(Role.CLASS_REVIEWER) or user.class_name is None:
        raise ForbiddenError("没有权限查看排名")
    if class_name is not None and class_name != user.class_name:
        raise ForbiddenError("只能查看本班排名")
