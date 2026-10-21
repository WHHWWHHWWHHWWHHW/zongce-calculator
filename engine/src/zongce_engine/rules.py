"""规则集：从已解析的规则 JSON（dict）构建，不读文件。

结构定义见仓库 ``rules/schema.json``。这里只做计算所需的校验；
完整的结构校验（如多余字段）由测试与 CI 用 JSON Schema 完成。
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol, cast

MoralField = Literal["political", "morality", "discipline", "integrity"]
BasicField = Literal["second_classroom", "public_service", "fitness_test", "dorm_check"]
MORAL_FIELDS: tuple[MoralField, ...] = ("political", "morality", "discipline", "integrity")
BASIC_FIELDS: tuple[BasicField, ...] = (
    "second_classroom",
    "public_service",
    "fitness_test",
    "dorm_check",
)

_DECIMAL = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
_RULE_ID = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*")
_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_JS_MATH_ROUND = "js_math_round"
_TRUNCATE = "truncate"
FinalRounding = Literal["js_math_round", "truncate"]


class RuleError(ValueError):
    """规则文件不合法。"""


class Rule(Protocol):
    """所有规则共有的标识与出处。"""

    @property
    def id(self) -> str: ...

    @property
    def source(self) -> str: ...


@dataclass(frozen=True, slots=True)
class RangeRule:
    """取值范围：得分 = clamp(值, min, max)。"""

    id: str
    name: str
    min: Decimal
    max: Decimal
    source: str


@dataclass(frozen=True, slots=True)
class FinalRule:
    """综测成绩 = 素质 ÷ quality_divisor × quality_weight + GPA × academic_weight，再舍入。"""

    id: str
    name: str
    academic_weight: Decimal
    quality_weight: Decimal
    quality_divisor: Decimal
    decimal_places: int
    source: str
    # 各项中间值（分项得分与小计）舍入到的小数位数；None 表示不舍入、只舍入最终结果（legacy 口径）。
    # 细则正文第六条“各项成绩精确到小数点后 4 位数”的另一种读法，见 docs/rules-issues.md R-005。
    intermediate_decimal_places: int | None = None
    # 最终结果的舍入方式：js_math_round（四舍五入，legacy 与办法原文）或 truncate（截去多余位数，
    # 学院导出表的实际做法，见 docs/rules-issues.md R-011）。
    rounding: FinalRounding = "js_math_round"


@dataclass(frozen=True, slots=True)
class AcademicRule:
    """学业水平评价（GPA）：空值记 0，不限范围。"""

    id: str
    name: str
    source: str


@dataclass(frozen=True, slots=True)
class TrimRule:
    """评议名单去极值：两端各去掉 js_round(n × ratio) 个。"""

    id: str
    name: str
    ratio: Decimal
    source: str


@dataclass(frozen=True, slots=True)
class MoralItemRule:
    """思想品德子项：直接给分或评议名单，得分限制在 [min, max]。"""

    id: str
    name: str
    field: MoralField
    min: Decimal
    max: Decimal
    source: str


@dataclass(frozen=True, slots=True)
class LinearCappedRule:
    """基础分：得分 = min(rate × x, cap)，空值记 0；与 legacy 一致，没有下限。"""

    id: str
    name: str
    field: BasicField
    rate: Decimal
    cap: Decimal
    source: str


@dataclass(frozen=True, slots=True)
class ThresholdRule:
    """基础分：x ≥ threshold 记 points 分，否则（含空值）记 0 分。"""

    id: str
    name: str
    field: BasicField
    threshold: Decimal
    points: Decimal
    source: str


@dataclass(frozen=True, slots=True)
class StepCappedRule:
    """基础分（阶梯计分，R-004）：x 未达到 min_value（含空值）记 0 分；达到后，
    得分 = min(floor(x ÷ step) × points_per_step, cap)，即全部积分都按阶梯计。负数记 0 分。"""

    id: str
    name: str
    field: BasicField
    step: Decimal
    points_per_step: Decimal
    cap: Decimal
    min_value: Decimal
    source: str


BasicRule = LinearCappedRule | ThresholdRule | StepCappedRule


@dataclass(frozen=True, slots=True)
class DeductionRule:
    """思想品德附减分（附件 1 第五、六条，R-001）：从各子项之和中扣除，再限制到 [min, max]。

    - ``max``：扣分合计上限，``None`` 表示不设上限；
    - ``floor_fields``：这些子项实际得分之和最多扣到 0（扣分不超过它们的得分之和），空表示不限制。
    两项同时设置时取较小者。“最高不超过三项的总和 20 分”的读法待负责人确认，所以两项都做成参数。
    """

    id: str
    name: str
    max: Decimal | None
    floor_fields: tuple[MoralField, ...]
    source: str


@dataclass(frozen=True, slots=True)
class QualityRule:
    """综合素质评价：明细模式限制在 [min, max]；direct 为直接输入总分模式。"""

    id: str
    name: str
    min: Decimal
    max: Decimal
    source: str
    direct: RangeRule


@dataclass(frozen=True, slots=True)
class MoralRule:
    """思想品德行为习惯：子项之和限制在 [min, max]。"""

    id: str
    name: str
    min: Decimal
    max: Decimal
    source: str
    trim: TrimRule
    items: tuple[MoralItemRule, ...]
    deduction: DeductionRule | None = None  # v1 没有附减分（R-001）


@dataclass(frozen=True, slots=True)
class CompetenceRule:
    """综合能力表现：clamp(基础分之和 + 能力分, min, max)。"""

    id: str
    name: str
    min: Decimal
    max: Decimal
    source: str
    basic: tuple[BasicRule, ...]
    ability: RangeRule


@dataclass(frozen=True, slots=True)
class RuleSet:
    """一个版本的完整计分规则。"""

    id: str
    version: str
    title: str
    final: FinalRule
    academic: AcademicRule
    quality: QualityRule
    moral: MoralRule
    competence: CompetenceRule

    @classmethod
    def from_dict(cls, data: object) -> "RuleSet":
        """从已解析的规则 JSON 构建并校验；不合法时抛出 ``RuleError``。"""
        root = _obj(data, "规则文件")
        version = _str(root, "version", "version")
        if not _VERSION.fullmatch(version):
            raise RuleError(f"version: 应为语义化版本号 X.Y.Z，实际为 {version!r}")
        ruleset = cls(
            id=_str(root, "id", "id"),
            version=version,
            title=_str(root, "title", "title"),
            final=_final(_obj(_get(root, "final", "final"), "final")),
            academic=_academic(_obj(_get(root, "academic", "academic"), "academic")),
            quality=_quality(_obj(_get(root, "quality", "quality"), "quality")),
            moral=_moral(_obj(_get(root, "moral", "moral"), "moral")),
            competence=_competence(_obj(_get(root, "competence", "competence"), "competence")),
        )
        seen: set[str] = set()
        for rule in ruleset.all_rules():
            if rule.id in seen:
                raise RuleError(f"重复的规则 id：{rule.id!r}")
            seen.add(rule.id)
        return ruleset

    def all_rules(self) -> tuple[Rule, ...]:
        """全部规则（含子规则），用于检查 id 唯一与出处完整。"""
        return (
            self.final,
            self.academic,
            self.quality,
            self.quality.direct,
            self.moral,
            self.moral.trim,
            *self.moral.items,
            *((self.moral.deduction,) if self.moral.deduction is not None else ()),
            self.competence,
            *self.competence.basic,
            self.competence.ability,
        )


# ---------- 解析辅助函数：每个函数只负责一种类型检查 ----------


def _obj(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuleError(f"{path}: 应为对象")
    return cast(Mapping[str, object], value)


def _get(obj: Mapping[str, object], key: str, path: str) -> object:
    if key not in obj:
        raise RuleError(f"{path}: 缺少该字段")
    return obj[key]


def _str(obj: Mapping[str, object], key: str, path: str) -> str:
    value = _get(obj, key, path)
    if not isinstance(value, str):
        raise RuleError(f"{path}: 应为字符串")
    return value


def _name(obj: Mapping[str, object], path: str) -> str:
    value = obj.get("name", "")
    if not isinstance(value, str):
        raise RuleError(f"{path}.name: 应为字符串")
    return value


def _id(obj: Mapping[str, object], path: str) -> str:
    value = _str(obj, "id", f"{path}.id")
    if not _RULE_ID.fullmatch(value):
        raise RuleError(f"{path}.id: 规则 id 格式不合法：{value!r}")
    return value


def _source(obj: Mapping[str, object], path: str) -> str:
    value = _str(obj, "source", f"{path}.source")
    if not value.strip():
        raise RuleError(f"{path}.source: 出处不能为空")
    return value


def _dec(obj: Mapping[str, object], key: str, path: str) -> Decimal:
    value = _get(obj, key, f"{path}.{key}")
    if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
        raise RuleError(f'{path}.{key}: 应为十进制数字符串（如 "0.75"），实际为 {value!r}')
    return Decimal(value)


def _int(obj: Mapping[str, object], key: str, path: str, low: int, high: int) -> int:
    value = _get(obj, key, f"{path}.{key}")
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise RuleError(f"{path}.{key}: 应为 {low}–{high} 的整数，实际为 {value!r}")
    return value


def _rounding(obj: Mapping[str, object], path: str, *, final: bool = False) -> FinalRounding:
    value = _get(obj, "rounding", f"{path}.rounding")
    allowed = (_JS_MATH_ROUND, _TRUNCATE) if final else (_JS_MATH_ROUND,)
    if value not in allowed:
        raise RuleError(f"{path}.rounding: 只支持 {' / '.join(allowed)}，实际为 {value!r}")
    return cast(FinalRounding, value)


def _list(obj: Mapping[str, object], key: str, path: str) -> list[Mapping[str, object]]:
    value = _get(obj, key, f"{path}.{key}")
    if not isinstance(value, list) or not value:
        raise RuleError(f"{path}.{key}: 应为非空数组")
    return [_obj(item, f"{path}.{key}[{i}]") for i, item in enumerate(value)]


def _limits(obj: Mapping[str, object], path: str) -> tuple[Decimal, Decimal]:
    low, high = _dec(obj, "min", path), _dec(obj, "max", path)
    if low > high:
        raise RuleError(f"{path}: min 不能大于 max")
    return low, high


def _field(obj: Mapping[str, object], path: str, allowed: tuple[str, ...], seen: set[str]) -> str:
    value = _str(obj, "field", f"{path}.field")
    if value not in allowed:
        raise RuleError(f"{path}.field: 未知字段 {value!r}，可选 {', '.join(allowed)}")
    if value in seen:
        raise RuleError(f"{path}.field: 字段 {value!r} 重复")
    seen.add(value)
    return value


def _range(obj: Mapping[str, object], path: str) -> RangeRule:
    low, high = _limits(obj, path)
    return RangeRule(_id(obj, path), _name(obj, path), low, high, _source(obj, path))


# ---------- 各部分规则 ----------


def _final(obj: Mapping[str, object]) -> FinalRule:
    path = "final"
    rounding = _rounding(obj, path, final=True)
    divisor = _dec(obj, "quality_divisor", path)
    if divisor <= 0:
        raise RuleError(f"{path}.quality_divisor: 必须大于 0")
    return FinalRule(
        id=_id(obj, path),
        name=_name(obj, path),
        academic_weight=_dec(obj, "academic_weight", path),
        quality_weight=_dec(obj, "quality_weight", path),
        quality_divisor=divisor,
        decimal_places=_int(obj, "decimal_places", path, 0, 10),
        source=_source(obj, path),
        intermediate_decimal_places=(
            None
            if obj.get("intermediate_decimal_places") is None
            else _int(obj, "intermediate_decimal_places", path, 0, 10)
        ),
        rounding=rounding,
    )


def _academic(obj: Mapping[str, object]) -> AcademicRule:
    return AcademicRule(_id(obj, "academic"), _name(obj, "academic"), _source(obj, "academic"))


def _quality(obj: Mapping[str, object]) -> QualityRule:
    path = "quality"
    low, high = _limits(obj, path)
    direct = _range(_obj(_get(obj, "direct", f"{path}.direct"), f"{path}.direct"), f"{path}.direct")
    return QualityRule(_id(obj, path), _name(obj, path), low, high, _source(obj, path), direct)


def _moral(obj: Mapping[str, object]) -> MoralRule:
    path = "moral"
    low, high = _limits(obj, path)
    trim_obj = _obj(_get(obj, "trim", f"{path}.trim"), f"{path}.trim")
    _rounding(trim_obj, f"{path}.trim")
    ratio = _dec(trim_obj, "ratio", f"{path}.trim")
    if not Decimal(0) <= ratio <= Decimal("0.5"):
        raise RuleError(f"{path}.trim.ratio: 应在 0–0.5 之间")
    trim = TrimRule(
        _id(trim_obj, f"{path}.trim"),
        _name(trim_obj, f"{path}.trim"),
        ratio,
        _source(trim_obj, f"{path}.trim"),
    )
    seen: set[str] = set()
    items: list[MoralItemRule] = []
    for i, item in enumerate(_list(obj, "items", path)):
        item_path = f"{path}.items[{i}]"
        field = cast(MoralField, _field(item, item_path, MORAL_FIELDS, seen))
        item_low, item_high = _limits(item, item_path)
        items.append(
            MoralItemRule(
                _id(item, item_path),
                _name(item, item_path),
                field,
                item_low,
                item_high,
                _source(item, item_path),
            )
        )
    deduction_obj = obj.get("deduction")
    deduction = (
        None
        if deduction_obj is None
        else _deduction(_obj(deduction_obj, f"{path}.deduction"), {i.field for i in items})
    )
    return MoralRule(
        _id(obj, path),
        _name(obj, path),
        low,
        high,
        _source(obj, path),
        trim,
        tuple(items),
        deduction,
    )


def _deduction(obj: Mapping[str, object], fields: set[MoralField]) -> DeductionRule:
    path = "moral.deduction"
    limit = None if obj.get("max") is None else _dec(obj, "max", path)
    if limit is not None and limit < 0:
        raise RuleError(f"{path}.max: 不能为负数")
    raw = _get(obj, "floor_fields", f"{path}.floor_fields")
    if not isinstance(raw, list):
        raise RuleError(f"{path}.floor_fields: 应为数组")
    seen: set[str] = set()
    floor: list[MoralField] = []
    for i, value in enumerate(raw):
        if value not in fields:
            raise RuleError(f"{path}.floor_fields[{i}]: 不是思想品德子项 {value!r}")
        if value in seen:
            raise RuleError(f"{path}.floor_fields[{i}]: 重复 {value!r}")
        seen.add(value)
        floor.append(cast(MoralField, value))
    return DeductionRule(_id(obj, path), _name(obj, path), limit, tuple(floor), _source(obj, path))


def _basic(obj: Mapping[str, object], path: str, seen: set[str]) -> BasicRule:
    kind = _str(obj, "type", f"{path}.type")
    field = cast(BasicField, _field(obj, path, BASIC_FIELDS, seen))
    rule_id, name, source = _id(obj, path), _name(obj, path), _source(obj, path)
    if kind == "linear_capped":
        return LinearCappedRule(
            rule_id, name, field, _dec(obj, "rate", path), _dec(obj, "cap", path), source
        )
    if kind == "threshold":
        return ThresholdRule(
            rule_id, name, field, _dec(obj, "threshold", path), _dec(obj, "points", path), source
        )
    if kind == "step_capped":
        step = _dec(obj, "step", path)
        if step <= 0:
            raise RuleError(f"{path}.step: 必须大于 0")
        min_value = Decimal(0) if obj.get("min_value") is None else _dec(obj, "min_value", path)
        return StepCappedRule(
            rule_id, name, field, step, _dec(obj, "points_per_step", path),
            _dec(obj, "cap", path), min_value, source,
        )  # fmt: skip
    raise RuleError(f"{path}.type: 未知的基础分规则类型 {kind!r}")


def _competence(obj: Mapping[str, object]) -> CompetenceRule:
    path = "competence"
    low, high = _limits(obj, path)
    seen: set[str] = set()
    basic = tuple(
        _basic(item, f"{path}.basic[{i}]", seen) for i, item in enumerate(_list(obj, "basic", path))
    )
    ability_path = f"{path}.ability"
    ability_obj = _obj(_get(obj, "ability", ability_path), ability_path)
    if _str(ability_obj, "field", f"{ability_path}.field") != "ability":
        raise RuleError(f"{ability_path}.field: 应为 'ability'")
    return CompetenceRule(
        _id(obj, path),
        _name(obj, path),
        low,
        high,
        _source(obj, path),
        basic,
        _range(ability_obj, ability_path),
    )
