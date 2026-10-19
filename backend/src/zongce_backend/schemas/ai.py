"""AI 辅助审核：名单比对的建议与批量确认。"""

from typing import Annotated

from pydantic import Field, StringConstraints

from zongce_ai import MatchStatus, Route

from .common import ApiModel


class AiStatus(ApiModel):
    provider: str = Field(description="none | local | remote")
    table_matching: bool = Field(description="Excel / CSV 名单比对，始终可用")
    image_recognition: bool = Field(description="图片、扫描件识别（需要 OCR 与大模型）")
    fast_track_threshold: str


class MatchSuggestionOut(ApiModel):
    row: int = Field(description="名单中的行号（表头为第 1 行）")
    student_username: str
    student_name: str | None = Field(description="账号中的姓名；学号不存在时为空")
    status: MatchStatus
    route: Route = Field(
        description="fast_track：可快速通过（仍需确认）；manual：人工复核；info：仅提示"
    )
    confidence: str
    declaration_id: int | None
    declaration_title: str | None
    form_option: str | None = Field(description="名单上的等级对应的选项编码")
    form_option_name: str | None
    declared_option: str | None
    declared_option_name: str | None
    reasons: list[str]


class AwardMatchResult(ApiModel):
    catalog_code: str
    catalog_name: str
    columns: dict[str, str] = Field(description="识别的表头 → 用途")
    ignored_columns: list[str]
    skipped_rows: list[int] = Field(description="学号为空而跳过的行号")
    out_of_scope_rows: int = Field(description="不属于本班、因而不显示的行数（班级审核员）")
    suggestions: list[MatchSuggestionOut]
    unmatched_declaration_ids: list[int] = Field(
        description="已提交但名单中没有的申报，照常人工审核"
    )
    counts: dict[str, int] = Field(description="按分流统计：fast_track / manual / info")


class FastTrackConfirm(ApiModel):
    declaration_ids: Annotated[list[int], Field(min_length=1, max_length=500)]
    source: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ] = Field(description="名单来源，写入审核理由，如“2025 年学科竞赛获奖名单.xlsx”")


class FastTrackItem(ApiModel):
    declaration_id: int
    ok: bool
    message: str


class FastTrackResult(ApiModel):
    approved: int
    items: list[FastTrackItem]
