"""学院成绩数据、核算、预估、排名与导出。"""

from urllib.parse import quote

from fastapi import APIRouter, Response, UploadFile

from ..deps import AdminUser, AppSettings, CurrentUser, DbSession, ReviewerUser
from ..models import ScoreField
from ..schemas.scores import (
    CollegeImportResult,
    CollegeRecordOut,
    CollegeRecordUpdate,
    ComputeRequest,
    ComputeResult,
    PreviewRequest,
    RankRow,
    ScoreOut,
    StoredScoreOut,
)
from ..services import college, ranking, scoring
from ..services.years import get_year
from .users import read_upload

router = APIRouter(tags=["成绩与核算"])
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post(
    "/score/preview",
    response_model=ScoreOut,
    summary="即时预估（不保存）",
    description="前端的即时预估一律调用本接口，前端不实现计分逻辑（CLAUDE.md §6）。"
    "分数均为十进制字符串。",
)
def preview(body: PreviewRequest, _: CurrentUser, db: DbSession) -> ScoreOut:
    return ScoreOut.of(scoring.preview(db, body))


@router.post(
    "/years/{year_id}/college-data/import",
    response_model=CollegeImportResult,
    summary="导入学院成绩表",
    description="表头需含“学号”；其余列按关键词识别（与 legacy 表格导入相同），"
    "如“学分绩点”“第二课堂”“体测”“政治素养”等。"
    "思想品德四项的单元格有多个数字时视为评议名单。“能力分”列会被忽略（能力分来自审核通过的申报）。",
)
def import_college_data(
    year_id: int, file: UploadFile, admin: AdminUser, db: DbSession, settings: AppSettings
) -> CollegeImportResult:
    data = read_upload(file, settings.max_upload_bytes)
    return college.import_table(db, admin, year_id, file.filename or "data.xlsx", data)


@router.get(
    "/years/{year_id}/college-data", response_model=list[CollegeRecordOut], summary="学院成绩数据"
)
def list_college_data(
    year_id: int, user: CurrentUser, db: DbSession, username: str | None = None
) -> list[CollegeRecordOut]:
    return [
        CollegeRecordOut.of(r, name)
        for r, name in college.list_records(db, user, year_id, username)
    ]


@router.put(
    "/years/{year_id}/college-data/{username}/{field}",
    response_model=CollegeRecordOut,
    summary="修改单项成绩数据（理由必填）",
)
def update_college_data(
    year_id: int,
    username: str,
    field: ScoreField,
    body: CollegeRecordUpdate,
    admin: AdminUser,
    db: DbSession,
) -> CollegeRecordOut:
    record = college.update_record(db, admin, year_id, username, field, body)
    return CollegeRecordOut.of(record, username)


@router.post("/years/{year_id}/scores/compute", response_model=ComputeResult, summary="核算")
def compute(year_id: int, body: ComputeRequest, admin: AdminUser, db: DbSession) -> ComputeResult:
    computed, changed = scoring.compute_year(db, admin, year_id, body.class_name, body.reason)
    return ComputeResult(computed=computed, changed=changed)


@router.get("/years/{year_id}/scores", response_model=list[StoredScoreOut], summary="核算结果")
def scores(
    year_id: int, user: CurrentUser, db: DbSession, class_name: str | None = None
) -> list[StoredScoreOut]:
    results = scoring.stored_scores(db, user, year_id, class_name)
    rows = {r.username: r for r in ranking.rank(results)}
    return [
        StoredScoreOut(
            student_username=r.student.username,
            student_name=r.student.name,
            class_name=r.student.class_name,
            final_score=rows[r.student.username].final_score,
            gpa=rows[r.student.username].gpa,
            quality_total=rows[r.student.username].quality_total,
            moral_total=rows[r.student.username].moral_total,
            competence_total=rows[r.student.username].competence_total,
            ability_total=rows[r.student.username].ability_total,
            rule_version_id=r.rule_version_id,
            computed_at=r.computed_at,
            detail=r.detail,
        )
        for r in results
    ]


def _ranking(
    year_id: int, user: CurrentUser, db: DbSession, class_name: str | None
) -> list[RankRow]:
    scoring.require_class_access(user, class_name)
    results = scoring.stored_scores(db, user, year_id, class_name)
    return ranking.rank(results)


@router.get("/years/{year_id}/rankings", response_model=list[RankRow], summary="班级排名")
def rankings(
    year_id: int, user: ReviewerUser, db: DbSession, class_name: str | None = None
) -> list[RankRow]:
    return _ranking(year_id, user, db, class_name)


@router.get(
    "/years/{year_id}/rankings/export",
    summary="导出排名 Excel",
    response_class=Response,
    responses={200: {"content": {_XLSX: {}}}},
)
def export_rankings(
    year_id: int, user: ReviewerUser, db: DbSession, class_name: str | None = None
) -> Response:
    year = get_year(db, year_id)
    data = ranking.export_xlsx(year, _ranking(year_id, user, db, class_name))
    filename = quote(f"{year.name}-综测排名{'-' + class_name if class_name else ''}.xlsx")
    return Response(
        data,
        media_type=_XLSX,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
