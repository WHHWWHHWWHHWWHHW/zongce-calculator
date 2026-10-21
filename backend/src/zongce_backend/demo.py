"""演示库：一条命令生成完整的合成演示数据（中期检查 V1.0 演示用，CLAUDE.md §8 M2）。

全部走业务层（service），与真实操作一样写审核记录和审计日志。只允许写入空库，避免混进真实数据。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings
from .errors import AppError
from .fake_data import class_name, college_rows, student_id, users_rows, xlsx_bytes
from .models import Role, User, UserRole, YearStatus
from .schemas.declarations import DeclarationCreate, ReviewRequest
from .schemas.publications import PublicationCreate
from .security import hash_password
from .services import college, declarations, publications, scoring, users, years
from .services.rules import create_rule_version
from .storage import LocalFileStorage

ADMIN_USERNAME = "demo_admin"
YEAR_NAME = "2025-2026"
MIN_STUDENTS = 10
EVIDENCE_PDF = b"%PDF-1.4\n% synthetic demo evidence\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n"


@dataclass(frozen=True)
class _Plan:
    """一名学生的一条申报及其处理方式。"""

    seat: int
    catalog_code: str
    title: str
    option_code: str | None = None
    team: tuple[int, int] | None = None  # (团队人数, 排名)
    claimed: str | None = None
    outcome: str = "approve"  # approve / adjust / reject / submitted / draft
    score: str | None = None
    reason: str = "材料齐全，与细则一致"
    evidence: bool = True


# 每班一组：覆盖通过、改分、驳回、待审核、草稿五种状态，以及团队项目和自定分值项目。
PLANS = (
    _Plan(2, "honor_university", "校级优秀学生", option_code="excellent"),
    _Plan(3, "competition", "某省级一类学科竞赛一等奖", option_code="c1_provincial_1", team=(3, 1)),
    _Plan(4, "cadre", "担任班委", option_code="member"),
    _Plan(
        5,
        "outstanding_deeds",
        "参与校园突发事件处置受学校表彰",
        claimed="4",
        outcome="adjust",
        score="3",
        reason="表彰文件为通报表扬，按细则核定 3 分",
    ),
    _Plan(
        6,
        "elective_course",
        "通选课附加分",
        option_code="above_80",
        outcome="reject",
        reason="成绩单未盖教务处章，请补充后重新提交",
    ),
    _Plan(7, "december_ninth_run", "一二·九长跑", option_code="second", outcome="submitted"),
    _Plan(8, "good_deeds", "拾金不昧受学院通报表扬", option_code="college", outcome="submitted"),
    _Plan(
        9,
        "dorm_inspection",
        "宿舍检查学年平均 90 分以上",
        option_code="above_90",
        outcome="draft",
        evidence=False,
    ),
)
REVIEWER_PLAN = _Plan(1, "cadre", "担任学生会部长", option_code="minister")  # 由管理员审核


@dataclass
class DemoSummary:
    admin: str
    year_id: int
    classes: list[str]
    reviewers: list[str]
    students: int
    declarations: dict[str, int] = field(default_factory=dict)
    publication_class: str = ""
    appeal_by: str = ""


def _load_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AppError(f"{path} 不是 JSON 对象")
    return data


def _user(db: Session, username: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    assert user is not None, username
    return user


def _declare(
    db: Session, settings: Settings, storage: LocalFileStorage, year_id: int, plan: _Plan,
    student: User, reviewer: User,
) -> str:  # fmt: skip
    data = DeclarationCreate(
        year_id=year_id,
        catalog_code=plan.catalog_code,
        option_code=plan.option_code,
        title=plan.title,
        description="（合成演示数据）",
        team_size=None if plan.team is None else plan.team[0],
        team_position=None if plan.team is None else plan.team[1],
        claimed_score=plan.claimed,
    )
    d = declarations.create(db, student, data)
    if plan.evidence:
        declarations.add_evidence(
            db, student, d.id, "证明材料（合成）.pdf", EVIDENCE_PDF, settings, storage
        )
    if plan.outcome == "draft":
        return "draft"
    declarations.submit(db, student, d.id)
    if plan.outcome == "submitted":
        return "submitted"
    request = ReviewRequest.model_validate(
        {"action": plan.outcome, "score": plan.score, "reason": plan.reason}
    )
    return declarations.review(db, reviewer, d.id, request).status.value


def seed_demo(
    db: Session,
    settings: Settings,
    *,
    password: str,
    rules_path: Path,
    catalog_path: Path,
    classes: int = 2,
    students: int = 30,
    seed: int = 1,
) -> DemoSummary:
    """向空库写入演示数据，返回摘要。所有演示账号使用同一个密码，且不要求首次改密。"""
    if classes < 1 or students < MIN_STUDENTS:
        raise AppError(f"至少 1 个班、每班至少 {MIN_STUDENTS} 人")
    if len(password) < 8:
        raise AppError("密码至少 8 位")
    if db.scalar(select(func.count()).select_from(User)):
        raise AppError("数据库里已有账号。演示数据只能写入空库，请换一个数据库文件")

    admin = User(
        username=ADMIN_USERNAME, name="演示管理员", password_hash=hash_password(password),
        must_change_password=False,
    )  # fmt: skip
    admin.role_rows.append(UserRole(role=Role.COLLEGE_ADMIN))
    db.add(admin)
    db.commit()

    version = create_rule_version(db, admin, _load_json(rules_path), _load_json(catalog_path))
    year = years.create_year(db, admin, YEAR_NAME, version.id)
    years.set_status(db, admin, year.id, YearStatus.OPEN)

    users.import_users(db, admin, "users.xlsx", xlsx_bytes(users_rows(classes, students)), settings)
    password_hash = hash_password(password)  # 演示账号共用一个密码，只算一次哈希
    for account in db.scalars(select(User).where(User.username != ADMIN_USERNAME)):
        account.password_hash, account.must_change_password = password_hash, False
    db.commit()
    college.import_table(
        db, admin, year.id, "college.xlsx", xlsx_bytes(college_rows(classes, students, seed))
    )

    storage = LocalFileStorage(settings.upload_dir)
    counts: dict[str, int] = {}
    for c in range(1, classes + 1):
        reviewer = _user(db, student_id(c, 1))
        for plan in PLANS:
            status = _declare(
                db, settings, storage, year.id, plan, _user(db, student_id(c, plan.seat)), reviewer
            )
            counts[status] = counts.get(status, 0) + 1
        status = _declare(db, settings, storage, year.id, REVIEWER_PLAN, reviewer, admin)
        counts[status] = counts.get(status, 0) + 1

    scoring.compute_year(db, admin, year.id, None, "演示数据：首次核算")
    first_class = class_name(1)
    publication = publications.create(
        db, admin, year.id, PublicationCreate(class_name=first_class), settings
    )
    appellant = _user(db, student_id(1, 6))
    publications.create_appeal(
        db, appellant, publication.id, "通选课附加分被驳回，已补充盖章成绩单，请复核。"
    )
    return DemoSummary(
        admin=ADMIN_USERNAME,
        year_id=year.id,
        classes=[class_name(c) for c in range(1, classes + 1)],
        reviewers=[student_id(c, 1) for c in range(1, classes + 1)],
        students=classes * students,
        declarations=counts,
        publication_class=first_class,
        appeal_by=appellant.username,
    )
