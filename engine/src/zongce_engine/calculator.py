"""计分：逐位复现 legacy ``calc()``（CLAUDE.md §4）。"""

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal, localcontext

from .models import ItemResult, MoralValue, PeerRatings, ScoreInput, ScoreResult
from .numbers import ZERO, clamp, round_js, trimmed_mean
from .rules import BasicRule, LinearCappedRule, MoralItemRule, RuleSet, TrimRule

# 计算精度（有效数字位数）。只有去极值平均的除法可能是无限小数；
# 50 位远超 4 位小数所需，不会把非边界值舍入成舍入边界。
_PRECISION = 50


def calculate(score_input: ScoreInput, rules: RuleSet) -> ScoreResult:
    """按规则计算一名学生的综测成绩，返回分项明细。"""
    with localcontext() as ctx:
        ctx.prec = _PRECISION
        return _calculate(score_input, rules)


def _or_zero(value: Decimal | None) -> Decimal:
    """对应 legacy 的 ``parseFloat(v) || 0``：空值、0、-0 都记为 0。"""
    return ZERO if value is None or value.is_zero() else value


def _limited(
    rule_id: str,
    raw: Decimal,
    low: Decimal,
    high: Decimal,
    peer_count: int | None = None,
    peer_trimmed_per_side: int | None = None,
) -> ItemResult:
    return ItemResult(
        rule_id=rule_id,
        score=clamp(raw, low, high),
        raw=raw,
        capped=raw > high,
        floored=raw < low,
        peer_count=peer_count,
        peer_trimmed_per_side=peer_trimmed_per_side,
    )


def _moral_item(rule: MoralItemRule, value: MoralValue, trim: TrimRule) -> ItemResult:
    if isinstance(value, PeerRatings):
        result = trimmed_mean(value.values, trim.ratio)
        return _limited(
            rule.id, result.mean, rule.min, rule.max, result.count, result.trimmed_per_side
        )
    if value is None:
        # legacy getPindeScore：isNaN(v) ? 0 : clamp(v, 0, max)
        return ItemResult(rule.id, ZERO)
    return _limited(rule.id, value, rule.min, rule.max)


def _basic_item(rule: BasicRule, value: Decimal | None) -> ItemResult:
    if isinstance(rule, LinearCappedRule):
        raw = _or_zero(value) * rule.rate
        return ItemResult(rule.id, min(raw, rule.cap), raw=raw, capped=raw > rule.cap)
    passed = value is not None and value >= rule.threshold
    return ItemResult(rule.id, rule.points if passed else ZERO, raw=value)


def _rounder(places: int | None) -> Callable[[Decimal], Decimal]:
    """中间值舍入（R-005 备选口径）；places 为 None 时原样返回（legacy 口径）。"""
    if places is None:
        return lambda value: value
    return lambda value: round_js(value, places)


def _calculate(score_input: ScoreInput, rules: RuleSet) -> ScoreResult:
    r = _rounder(rules.final.intermediate_decimal_places)

    def fix(item: ItemResult) -> ItemResult:
        return replace(item, score=r(item.score))

    gpa = r(_or_zero(score_input.gpa))
    items = [ItemResult(rules.academic.id, gpa, raw=score_input.gpa)]
    moral_total: Decimal | None = None
    competence_total: Decimal | None = None
    basic_total: Decimal | None = None

    if score_input.quality_mode == "direct":
        direct = rules.quality.direct
        quality = fix(
            _limited(direct.id, _or_zero(score_input.quality_direct), direct.min, direct.max)
        )
        items.append(quality)
    else:
        moral_items = [
            fix(_moral_item(rule, score_input.moral_value(rule.field), rules.moral.trim))
            for rule in rules.moral.items
        ]
        moral = fix(
            _limited(
                rules.moral.id,
                sum((i.score for i in moral_items), ZERO),
                rules.moral.min,
                rules.moral.max,
            )
        )
        competence_rule = rules.competence
        basic_items = [
            fix(_basic_item(rule, score_input.basic_value(rule.field)))
            for rule in competence_rule.basic
        ]
        basic_total = sum((i.score for i in basic_items), ZERO)
        ability_rule = competence_rule.ability
        ability = fix(
            _limited(
                ability_rule.id, _or_zero(score_input.ability), ability_rule.min, ability_rule.max
            )
        )
        competence = fix(
            _limited(
                competence_rule.id,
                basic_total + ability.score,
                competence_rule.min,
                competence_rule.max,
            )
        )
        quality = fix(
            _limited(
                rules.quality.id,
                moral.score + competence.score,
                rules.quality.min,
                rules.quality.max,
            )
        )
        moral_total, competence_total = moral.score, competence.score
        items += [*moral_items, moral, *basic_items, ability, competence, quality]

    final = rules.final
    final_raw = (
        quality.score / final.quality_divisor * final.quality_weight + gpa * final.academic_weight
    )
    final_score = round_js(final_raw, final.decimal_places)
    items.append(ItemResult(final.id, final_score, raw=final_raw))

    return ScoreResult(
        rules_id=rules.id,
        rules_version=rules.version,
        quality_mode=score_input.quality_mode,
        final_score=final_score,
        final_score_raw=final_raw,
        gpa=gpa,
        quality_total=quality.score,
        moral_total=moral_total,
        competence_total=competence_total,
        basic_total=basic_total,
        items=tuple(items),
    )
