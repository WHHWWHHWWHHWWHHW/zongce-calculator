"""学院成绩数据、核算、预估、排名。"""

from typing import Literal, Self

from pydantic import Field, model_validator

from zongce_engine import ItemResult, ScoreResult, format_score

from ..models import CollegeRecord, ScoreField
from .common import ApiModel, DecimalStr, Reason, UtcDatetime, dec_str


class MoralInput(ApiModel):
    """思想品德子项，三选一：直接得分、评议名单（数组）、评议名单文本（legacy 文本框格式）。"""

    score: DecimalStr | None = None
    ratings: list[DecimalStr] | None = Field(default=None, max_length=500)
    ratings_text: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def _one_of(self) -> Self:
        given = [v for v in (self.score, self.ratings, self.ratings_text) if v is not None]
        if len(given) != 1:
            raise ValueError("score、ratings、ratings_text 必须且只能填写一项")
        return self


class PreviewRequest(ApiModel):
    rule_version_id: int | None = Field(default=None, description="省略时使用最新的规则版本")
    gpa: DecimalStr | None = None
    quality_mode: Literal["detail", "direct"] = "detail"
    quality_direct: DecimalStr | None = None
    political: MoralInput | None = None
    morality: MoralInput | None = None
    discipline: MoralInput | None = None
    integrity: MoralInput | None = None
    second_classroom: DecimalStr | None = None
    public_service: DecimalStr | None = None
    fitness_test: DecimalStr | None = None
    dorm_check: DecimalStr | None = None
    ability: DecimalStr | None = None


class ItemOut(ApiModel):
    rule_id: str
    score: str
    raw: str | None
    capped: bool
    floored: bool
    peer_count: int | None
    peer_trimmed_per_side: int | None

    @classmethod
    def of(cls, item: ItemResult) -> "ItemOut":
        return cls(
            rule_id=item.rule_id,
            score=format(item.score, "f"),
            raw=dec_str(item.raw),
            capped=item.capped,
            floored=item.floored,
            peer_count=item.peer_count,
            peer_trimmed_per_side=item.peer_trimmed_per_side,
        )


class ScoreOut(ApiModel):
    """计分结果。各合计值为 4 位小数的展示值；精确值见 items[].raw / score。"""

    rules_id: str
    rules_version: str
    final_score: str
    gpa: str
    quality_total: str
    moral_total: str | None
    competence_total: str | None
    items: list[ItemOut]

    @classmethod
    def of(cls, result: ScoreResult) -> "ScoreOut":
        def fmt(value: object) -> str | None:
            return None if value is None else format_score(value)  # type: ignore[arg-type]

        return cls(
            rules_id=result.rules_id,
            rules_version=result.rules_version,
            final_score=format_score(result.final_score),
            gpa=format_score(result.gpa),
            quality_total=format_score(result.quality_total),
            moral_total=fmt(result.moral_total),
            competence_total=fmt(result.competence_total),
            items=[ItemOut.of(i) for i in result.items],
        )


class CollegeImportResult(ApiModel):
    batch_id: int
    rows: int
    changed: int
    unchanged: int
    mapped_columns: dict[str, str]
    ignored_columns: list[str]
    errors: list[dict[str, str | int]]


class CollegeRecordOut(ApiModel):
    student_username: str
    field: ScoreField
    value: str | None
    ratings: list[str] | None
    updated_at: UtcDatetime

    @classmethod
    def of(cls, record: CollegeRecord, username: str) -> "CollegeRecordOut":
        return cls(
            student_username=username,
            field=record.field,
            value=dec_str(record.value),
            ratings=record.ratings,
            updated_at=record.updated_at,
        )


class CollegeRecordUpdate(ApiModel):
    value: DecimalStr | None = None
    ratings: list[DecimalStr] | None = Field(default=None, min_length=1, max_length=500)
    reason: Reason

    @model_validator(mode="after")
    def _one_of(self) -> Self:
        if (self.value is None) == (self.ratings is None):
            raise ValueError("value 与 ratings 必须且只能填写一项")
        return self


class ComputeRequest(ApiModel):
    class_name: str | None = None
    reason: Reason = "核算"


class ComputeResult(ApiModel):
    computed: int
    changed: int


class StoredScoreOut(ApiModel):
    student_username: str
    student_name: str
    class_name: str | None
    final_score: str
    gpa: str
    quality_total: str
    moral_total: str | None
    competence_total: str | None
    ability_total: str
    rule_version_id: int
    computed_at: UtcDatetime
    detail: dict[str, object]


class RankRow(ApiModel):
    rank: int
    class_name: str | None
    username: str
    name: str
    final_score: str
    gpa: str
    quality_total: str
    moral_total: str | None
    competence_total: str | None
    ability_total: str
