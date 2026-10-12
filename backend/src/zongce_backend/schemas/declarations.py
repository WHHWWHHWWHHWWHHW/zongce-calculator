"""能力分申报、证明材料与审核。"""

from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from ..models import Declaration, DeclarationStatus, EvidenceFile, ReviewAction, ReviewRecord
from .common import ApiModel, NonNegativeDecimalStr, Reason, dec_str

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class DeclarationCreate(ApiModel):
    year_id: int
    catalog_code: str = Field(max_length=64)
    option_code: str | None = Field(default=None, max_length=64)
    title: Title
    description: str = Field(default="", max_length=5000)
    team_size: int | None = Field(default=None, ge=1, le=100)
    team_position: int | None = Field(default=None, ge=1, le=100)
    concurrent_rank: int | None = Field(default=None, ge=1, le=10)
    quantity: int | None = Field(default=None, ge=1, le=1000)
    claimed_score: NonNegativeDecimalStr | None = None


class DeclarationUpdate(ApiModel):
    option_code: str | None = Field(default=None, max_length=64)
    title: Title | None = None
    description: str | None = Field(default=None, max_length=5000)
    team_size: int | None = Field(default=None, ge=1, le=100)
    team_position: int | None = Field(default=None, ge=1, le=100)
    concurrent_rank: int | None = Field(default=None, ge=1, le=10)
    quantity: int | None = Field(default=None, ge=1, le=1000)
    claimed_score: NonNegativeDecimalStr | None = None


class EvidenceOut(ApiModel):
    id: int
    original_name: str
    content_type: str
    size: int
    sha256: str
    created_at: datetime

    @classmethod
    def of(cls, item: EvidenceFile) -> "EvidenceOut":
        return cls.model_validate(item)


class DeclarationOut(ApiModel):
    id: int
    year_id: int
    student_id: int
    student_username: str
    student_name: str
    class_name: str | None
    catalog_code: str
    option_code: str | None
    title: str
    description: str
    team_size: int | None
    team_position: int | None
    concurrent_rank: int | None
    quantity: int | None
    claimed_score: str | None
    suggested_score: str | None
    approved_score: str | None
    status: DeclarationStatus
    submitted_at: datetime | None
    reviewed_at: datetime | None
    reviewer_id: int | None
    evidence: list[EvidenceOut]

    @classmethod
    def of(cls, d: Declaration) -> "DeclarationOut":
        return cls(
            id=d.id,
            year_id=d.year_id,
            student_id=d.student_id,
            student_username=d.student.username,
            student_name=d.student.name,
            class_name=d.student.class_name,
            catalog_code=d.catalog_code,
            option_code=d.option_code,
            title=d.title,
            description=d.description,
            team_size=d.team_size,
            team_position=d.team_position,
            concurrent_rank=d.concurrent_rank,
            quantity=d.quantity,
            claimed_score=dec_str(d.claimed_score),
            suggested_score=dec_str(d.suggested_score),
            approved_score=dec_str(d.approved_score),
            status=d.status,
            submitted_at=d.submitted_at,
            reviewed_at=d.reviewed_at,
            reviewer_id=d.reviewer_id,
            evidence=[EvidenceOut.of(e) for e in d.evidence],
        )


class ReviewRequest(ApiModel):
    action: ReviewAction
    score: NonNegativeDecimalStr | None = None
    reason: Reason


class ReviewOut(ApiModel):
    id: int
    declaration_id: int
    reviewer_id: int
    action: ReviewAction
    score_before: str | None
    score_after: str | None
    reason: str
    created_at: datetime

    @classmethod
    def of(cls, r: ReviewRecord) -> "ReviewOut":
        return cls(
            id=r.id,
            declaration_id=r.declaration_id,
            reviewer_id=r.reviewer_id,
            action=r.action,
            score_before=dec_str(r.score_before),
            score_after=dec_str(r.score_after),
            reason=r.reason,
            created_at=r.created_at,
        )
