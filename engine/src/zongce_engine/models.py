"""计分输入与输出的数据结构。"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from .rules import BasicField, MoralField

QualityMode = Literal["detail", "direct"]
"""综合素质评价的录入方式：``detail`` 按细则计算，``direct`` 直接输入总分。"""

_QUALITY_MODES: tuple[QualityMode, ...] = ("detail", "direct")
_DECIMAL_FIELDS = (
    "gpa",
    "quality_direct",
    "second_classroom",
    "public_service",
    "fitness_test",
    "dorm_check",
    "ability",
    "moral_deduction",
)
_MORAL_FIELDS = ("political", "morality", "discipline", "integrity")


def _check_decimal(value: object, name: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} 必须是 Decimal（引擎内禁止浮点数），实际为 {type(value).__name__}")
    if not value.is_finite():
        raise ValueError(f"{name} 必须是有限数，实际为 {value}")


@dataclass(frozen=True, slots=True)
class PeerRatings:
    """全班评议打分名单（去极值后求平均）。"""

    values: tuple[Decimal, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.values, tuple):
            raise TypeError("PeerRatings.values 必须是 tuple")
        for i, value in enumerate(self.values):
            _check_decimal(value, f"PeerRatings.values[{i}]")


MoralValue = Decimal | PeerRatings | None
"""思想品德子项：直接得分、评议名单，或空（记 0 分）。"""


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreInput:
    """一名学生的计分输入。字段名与 CLAUDE.md §4 一致；``None`` 表示未填写。"""

    gpa: Decimal | None = None
    quality_mode: QualityMode = "detail"
    quality_direct: Decimal | None = None
    political: MoralValue = None
    morality: MoralValue = None
    discipline: MoralValue = None
    integrity: MoralValue = None
    second_classroom: Decimal | None = None
    public_service: Decimal | None = None
    fitness_test: Decimal | None = None
    dorm_check: Decimal | None = None
    ability: Decimal | None = None
    moral_deduction: Decimal | None = None  # 思想品德附减分合计（R-001），规则没有减分时不起作用

    def __post_init__(self) -> None:
        if self.quality_mode not in _QUALITY_MODES:
            raise ValueError(f"quality_mode 应为 detail 或 direct，实际为 {self.quality_mode!r}")
        for name in _DECIMAL_FIELDS:
            value = getattr(self, name)
            if value is not None:
                _check_decimal(value, name)
        if self.moral_deduction is not None and self.moral_deduction < 0:
            raise ValueError(f"moral_deduction 不能为负数，实际为 {self.moral_deduction}")
        for name in _MORAL_FIELDS:
            value = getattr(self, name)
            if value is not None and not isinstance(value, PeerRatings):
                _check_decimal(value, name)

    def moral_value(self, name: MoralField) -> MoralValue:
        return {
            "political": self.political,
            "morality": self.morality,
            "discipline": self.discipline,
            "integrity": self.integrity,
        }[name]

    def basic_value(self, name: BasicField) -> Decimal | None:
        return {
            "second_classroom": self.second_classroom,
            "public_service": self.public_service,
            "fitness_test": self.fitness_test,
            "dorm_check": self.dorm_check,
        }[name]


@dataclass(frozen=True, slots=True)
class ItemResult:
    """一条规则的计算结果。

    - ``raw``：限幅（clamp / 封顶）前的值；阈值类规则为原始成绩；未填写为 ``None``。
    - ``capped``：是否触发上限（封顶）；``floored``：是否触发下限。
    - ``peer_count`` / ``peer_trimmed_per_side``：评议名单的人数与每端去掉的人数。
    """

    rule_id: str
    score: Decimal
    raw: Decimal | None = None
    capped: bool = False
    floored: bool = False
    peer_count: int | None = None
    peer_trimmed_per_side: int | None = None


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """计分结果与分项明细。除 ``final_score`` 外，各值都未舍入。"""

    rules_id: str
    rules_version: str
    quality_mode: QualityMode
    final_score: Decimal
    final_score_raw: Decimal
    gpa: Decimal
    quality_total: Decimal
    moral_total: Decimal | None
    competence_total: Decimal | None
    basic_total: Decimal | None
    items: tuple[ItemResult, ...] = field(default=())

    def item(self, rule_id: str) -> ItemResult:
        """按规则 id 取分项明细。"""
        for result in self.items:
            if result.rule_id == rule_id:
                return result
        raise KeyError(rule_id)
