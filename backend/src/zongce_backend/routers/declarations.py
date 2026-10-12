"""能力分申报、证明材料、审核。"""

from urllib.parse import quote

from fastapi import APIRouter, Response, UploadFile

from ..deps import AppSettings, CurrentUser, DbSession, Storage
from ..models import DeclarationStatus
from ..schemas.declarations import (
    DeclarationCreate,
    DeclarationOut,
    DeclarationUpdate,
    EvidenceOut,
    ReviewOut,
    ReviewRequest,
)
from ..services import declarations as service
from .users import read_upload

router = APIRouter(tags=["申报与审核"])


@router.post(
    "/declarations", response_model=DeclarationOut, status_code=201, summary="新建申报（草稿）"
)
def create(body: DeclarationCreate, user: CurrentUser, db: DbSession) -> DeclarationOut:
    return DeclarationOut.of(service.create(db, user, body))


@router.get(
    "/declarations",
    response_model=list[DeclarationOut],
    summary="申报列表",
    description="mine=true 只看自己的；否则学院管理员看全部、班级审核员看本班、学生看自己的。",
)
def list_declarations(
    user: CurrentUser,
    db: DbSession,
    mine: bool = False,
    year_id: int | None = None,
    status: DeclarationStatus | None = None,
    class_name: str | None = None,
) -> list[DeclarationOut]:
    items = service.list_for(
        db, user, mine=mine, year_id=year_id, status=status, class_name=class_name
    )
    return [DeclarationOut.of(d) for d in items]


@router.get("/declarations/{declaration_id}", response_model=DeclarationOut, summary="申报详情")
def get(declaration_id: int, user: CurrentUser, db: DbSession) -> DeclarationOut:
    return DeclarationOut.of(service.get_for(db, user, declaration_id))


@router.patch("/declarations/{declaration_id}", response_model=DeclarationOut, summary="修改申报")
def update(
    declaration_id: int, body: DeclarationUpdate, user: CurrentUser, db: DbSession
) -> DeclarationOut:
    return DeclarationOut.of(service.update(db, user, declaration_id, body))


@router.post(
    "/declarations/{declaration_id}/submit", response_model=DeclarationOut, summary="提交审核"
)
def submit(declaration_id: int, user: CurrentUser, db: DbSession) -> DeclarationOut:
    return DeclarationOut.of(service.submit(db, user, declaration_id))


@router.post(
    "/declarations/{declaration_id}/withdraw", response_model=DeclarationOut, summary="撤回"
)
def withdraw(declaration_id: int, user: CurrentUser, db: DbSession) -> DeclarationOut:
    return DeclarationOut.of(service.withdraw(db, user, declaration_id))


@router.post(
    "/declarations/{declaration_id}/evidence",
    response_model=EvidenceOut,
    status_code=201,
    summary="上传证明材料（PDF/PNG/JPEG）",
)
def upload_evidence(
    declaration_id: int,
    file: UploadFile,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    storage: Storage,
) -> EvidenceOut:
    data = read_upload(file, settings.max_upload_bytes)
    evidence = service.add_evidence(
        db, user, declaration_id, file.filename or "", data, settings, storage
    )
    return EvidenceOut.of(evidence)


@router.get(
    "/evidence/{evidence_id}",
    summary="下载证明材料",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
def download_evidence(
    evidence_id: int, user: CurrentUser, db: DbSession, storage: Storage
) -> Response:
    evidence, data = service.read_evidence(db, user, evidence_id, storage)
    disposition = f"attachment; filename*=UTF-8''{quote(evidence.original_name)}"
    return Response(
        data, media_type=evidence.content_type, headers={"Content-Disposition": disposition}
    )


@router.delete("/evidence/{evidence_id}", status_code=204, summary="删除证明材料（草稿或被驳回时）")
def delete_evidence(evidence_id: int, user: CurrentUser, db: DbSession, storage: Storage) -> None:
    service.delete_evidence(db, user, evidence_id, storage)


@router.post(
    "/declarations/{declaration_id}/review",
    response_model=DeclarationOut,
    summary="审核：通过 / 改分 / 驳回（理由必填）",
)
def review(
    declaration_id: int, body: ReviewRequest, user: CurrentUser, db: DbSession
) -> DeclarationOut:
    return DeclarationOut.of(service.review(db, user, declaration_id, body))


@router.get(
    "/declarations/{declaration_id}/reviews", response_model=list[ReviewOut], summary="审核记录"
)
def reviews(declaration_id: int, user: CurrentUser, db: DbSession) -> list[ReviewOut]:
    return [ReviewOut.of(r) for r in service.reviews_of(db, user, declaration_id)]
