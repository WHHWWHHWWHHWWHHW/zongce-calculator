"""能力分申报目录（rules/ability-catalog-*.json）：结构校验、建议分、分组封顶。"""

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import AppError
from .schemas.common import NonNegativeDecimalStr

_CODE = r"^[a-z][a-z0-9_]*$"
_FOUR_PLACES = Decimal("0.0001")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CatalogOption(_Model):
    code: str = Field(pattern=_CODE)
    name: str = Field(min_length=1)
    score: NonNegativeDecimalStr


class CapGroup(_Model):
    code: str = Field(pattern=_CODE)
    name: str = Field(min_length=1)
    max: NonNegativeDecimalStr
    source: str = Field(min_length=1)


class CatalogItem(_Model):
    code: str = Field(pattern=_CODE)
    group: str = Field(min_length=1)
    name: str = Field(min_length=1)
    scoring: Literal["fixed", "per_unit", "manual"]
    options: list[CatalogOption] = []
    unit_name: str | None = None
    unit_score: NonNegativeDecimalStr | None = None
    min_score: NonNegativeDecimalStr | None = None
    max_score: NonNegativeDecimalStr | None = None
    team: bool = False
    concurrent: bool = False
    cap_group: str | None = None
    notes: str = ""
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.scoring == "fixed" and not self.options:
            raise ValueError(f"{self.code}: fixed 类型必须有 options")
        if self.scoring != "fixed" and self.options:
            raise ValueError(f"{self.code}: 只有 fixed 类型可以有 options")
        if (self.scoring == "per_unit") != (self.unit_score is not None):
            raise ValueError(f"{self.code}: per_unit 类型必须且只能它有 unit_score")
        codes = [o.code for o in self.options]
        if len(codes) != len(set(codes)):
            raise ValueError(f"{self.code}: 选项编码重复")
        return self

    def option(self, code: str | None) -> CatalogOption | None:
        return next((o for o in self.options if o.code == code), None)


class AbilityCatalog(_Model):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_document: str = Field(min_length=1)
    notes: str = ""
    concurrent_coefficients: list[NonNegativeDecimalStr] = Field(min_length=1)
    caps: list[CapGroup] = []
    items: list[CatalogItem] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        codes = [i.code for i in self.items]
        if len(codes) != len(set(codes)):
            raise ValueError("申报项目编码重复")
        cap_codes = {c.code for c in self.caps}
        for item in self.items:
            if item.cap_group is not None and item.cap_group not in cap_codes:
                raise ValueError(f"{item.code}: 未定义的封顶分组 {item.cap_group}")
        return self

    def item(self, code: str) -> CatalogItem:
        for item in self.items:
            if item.code == code:
                return item
        raise AppError(f"未知的申报项目：{code}")

    def cap(self, code: str) -> Decimal:
        return next(Decimal(c.max) for c in self.caps if c.code == code)


def suggested_score(
    item: CatalogItem,
    *,
    option_code: str | None,
    team_size: int | None,
    team_position: int | None,
    concurrent_rank: int | None,
    quantity: int | None,
    coefficients: list[str],
) -> Decimal | None:
    """按目录计算建议分；人工给分（manual）项目返回 None。参数不合法时抛出 AppError。"""
    if item.scoring == "fixed":
        option = item.option(option_code)
        if option is None:
            raise AppError(f"请为“{item.name}”选择有效的级别/奖项")
        base = Decimal(option.score)
    elif option_code is not None:
        raise AppError(f"“{item.name}”没有级别/奖项可选")
    if item.scoring == "per_unit":
        if quantity is None or quantity < 1:
            raise AppError(f"请填写“{item.name}”的数量（{item.unit_name or '次'}）")
        base = Decimal(str(item.unit_score)) * quantity
    elif quantity is not None:
        raise AppError(f"“{item.name}”不按数量计分")

    if item.team:
        if (team_size is None) != (team_position is None):
            raise AppError("多人项目需同时填写完成总人数和本人位次")
        if (
            team_size is not None
            and team_position is not None
            and not (1 <= team_position <= team_size <= 100)
        ):
            raise AppError("位次须在 1 到总人数之间，总人数不超过 100")
    elif team_size is not None or team_position is not None:
        raise AppError(f"“{item.name}”不是多人项目，不需要填写人数和位次")

    if item.concurrent:
        if concurrent_rank is not None and not 1 <= concurrent_rank <= len(coefficients):
            raise AppError(f"兼任职务的高低排序须在 1 到 {len(coefficients)} 之间")
    elif concurrent_rank is not None:
        raise AppError(f"“{item.name}”不涉及兼任职务排序")

    if item.scoring == "manual":
        return None
    if team_size is not None and team_position is not None:
        # 附加分值 = 附加分值标准 × (N − M + 1) / (1 + 2 + … + N)
        base = base * (team_size - team_position + 1) / Decimal(team_size * (team_size + 1) // 2)
    if concurrent_rank is not None:
        base = base * Decimal(coefficients[concurrent_rank - 1])
    return base.quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)


def aggregate(
    catalog: AbilityCatalog, scores: Iterable[tuple[str, Decimal]]
) -> tuple[Decimal, list[dict[str, str | bool]]]:
    """按封顶分组汇总已通过申报的得分，返回 (能力分合计, 各组明细)。总分 50 封顶由计分引擎处理。"""
    grouped: dict[str | None, Decimal] = {}
    for item_code, score in scores:
        group = catalog.item(item_code).cap_group
        grouped[group] = grouped.get(group, Decimal(0)) + score
    total = Decimal(0)
    detail: list[dict[str, str | bool]] = []
    for group, subtotal in sorted(grouped.items(), key=lambda kv: kv[0] or ""):
        counted = subtotal if group is None else min(subtotal, catalog.cap(group))
        total += counted
        detail.append(
            {
                "cap_group": group or "",
                "subtotal": format(subtotal, "f"),
                "counted": format(counted, "f"),
                "capped": counted != subtotal,
            }
        )
    return total, detail
