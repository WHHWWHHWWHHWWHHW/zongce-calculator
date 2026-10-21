"""AI 辅助审核：名单比对（只给建议）与批量确认。"""

from typing import Annotated

from fastapi import APIRouter, Form, UploadFile

from ..deps import AppSettings, CurrentUser, DbSession, ReviewerUser
from ..schemas.ai import AiStatus, AwardMatchResult, FastTrackConfirm, FastTrackResult
from ..services import ai_review
from .users import read_upload

router = APIRouter(tags=["AI 辅助审核"])


@router.get("/ai/status", response_model=AiStatus, summary="AI 功能状态（AI_PROVIDER）")
def ai_status(_: CurrentUser, settings: AppSettings) -> AiStatus:
    return ai_review.status(settings)


@router.post(
    "/years/{year_id}/ai/award-match",
    response_model=AwardMatchResult,
    summary="上传学院名单，与待审核申报比对（只给建议，不改分）",
    description="两种名单：① .xlsx / .csv 表格，表头需含“学号”，"
    "等级写在“级别”“等级”“奖项”“名次”等列，"
    "context 是对整张表都成立的说明（如“一类赛事”）；② 带文字层的 .pdf 或 .txt 活动获奖名单"
    "（活动名称、等级与分值、“班级 姓名”），按班级 + 姓名找学生、按分值定选项，"
    "context 为活动默认级别（缺省“院级”）。图片和没有文字层的 PDF 需要 OCR，"
    "AI_PROVIDER=none 时返回 400。班级审核员只看到本班学生。",
)
def award_match(
    year_id: int,
    file: UploadFile,
    catalog_code: Annotated[str, Form(max_length=64)],
    user: ReviewerUser,
    db: DbSession,
    settings: AppSettings,
    context: Annotated[str, Form(max_length=100)] = "",
) -> AwardMatchResult:
    data = read_upload(file, settings.max_upload_bytes)
    return ai_review.award_match(
        db, user, year_id, catalog_code, file.filename or "list.xlsx", data, context, settings
    )


@router.post(
    "/years/{year_id}/ai/fast-track",
    response_model=FastTrackResult,
    summary="批量确认“可快速通过”的申报",
    description="逐条按“通过”审核（建议分），写审核记录与审计日志；单条失败不影响其他条目。",
)
def confirm_fast_track(
    year_id: int, body: FastTrackConfirm, user: ReviewerUser, db: DbSession
) -> FastTrackResult:
    return ai_review.confirm_fast_track(db, user, year_id, body)
