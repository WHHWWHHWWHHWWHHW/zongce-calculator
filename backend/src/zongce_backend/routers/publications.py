"""公示与异议。"""

from fastapi import APIRouter

from ..deps import AdminUser, AppSettings, CurrentUser, DbSession
from ..schemas.publications import (
    AppealCreate,
    AppealOut,
    AppealResolve,
    PublicationCreate,
    PublicationOut,
)
from ..services import publications as service

router = APIRouter(tags=["公示与异议"])


@router.post(
    "/years/{year_id}/publications",
    response_model=PublicationOut,
    status_code=201,
    summary="发布班级公示（快照当前核算结果，默认 3 天）",
)
def create(
    year_id: int, body: PublicationCreate, admin: AdminUser, db: DbSession, settings: AppSettings
) -> PublicationOut:
    return service.to_out(service.create(db, admin, year_id, body, settings))


@router.get("/publications", response_model=list[PublicationOut], summary="公示列表")
def list_publications(
    user: CurrentUser, db: DbSession, year_id: int | None = None
) -> list[PublicationOut]:
    return [service.to_out(p) for p in service.list_for(db, user, year_id)]


@router.get("/publications/{publication_id}", response_model=PublicationOut, summary="公示详情")
def get(publication_id: int, user: CurrentUser, db: DbSession) -> PublicationOut:
    return service.to_out(service.get(db, user, publication_id))


@router.post(
    "/publications/{publication_id}/close", response_model=PublicationOut, summary="提前结束公示"
)
def close(publication_id: int, admin: AdminUser, db: DbSession) -> PublicationOut:
    return service.to_out(service.close(db, admin, publication_id))


@router.post(
    "/publications/{publication_id}/appeals",
    response_model=AppealOut,
    status_code=201,
    summary="提出异议（公示期内，本班学生）",
)
def create_appeal(
    publication_id: int, body: AppealCreate, user: CurrentUser, db: DbSession
) -> AppealOut:
    return AppealOut.model_validate(service.create_appeal(db, user, publication_id, body.content))


@router.get("/appeals", response_model=list[AppealOut], summary="异议列表（学生只看自己的）")
def list_appeals(
    user: CurrentUser, db: DbSession, publication_id: int | None = None
) -> list[AppealOut]:
    return [AppealOut.model_validate(a) for a in service.list_appeals(db, user, publication_id)]


@router.post("/appeals/{appeal_id}/resolve", response_model=AppealOut, summary="处理异议")
def resolve(appeal_id: int, body: AppealResolve, admin: AdminUser, db: DbSession) -> AppealOut:
    return AppealOut.model_validate(service.resolve_appeal(db, admin, appeal_id, body))
