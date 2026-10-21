"""计分：分项明细、封顶标记、两种综合素质模式、输入校验。"""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from zongce_engine import PeerRatings, RuleSet, ScoreInput, calculate


def _ratings(*values: str) -> PeerRatings:
    return PeerRatings(tuple(D(v) for v in values))


def test_g3_breakdown_and_cap_flags(rules: RuleSet) -> None:
    result = calculate(
        ScoreInput(
            gpa=D("4.0"),
            political=_ratings("1", "2", "3", "4", "10"),
            morality=D("12"),
            discipline=D("5"),
            integrity=D("5"),
            second_classroom=D("20"),
            public_service=D("12"),
            fitness_test=D("59"),
            dorm_check=D("60"),
            ability=D("60"),
        ),
        rules,
    )
    assert result.rules_id == "ujn-v1"
    assert result.rules_version == "1.0.0"
    assert result.quality_mode == "detail"
    assert str(result.final_score) == "4.1000"
    assert result.final_score_raw == D("4.1")
    assert result.moral_total == D("23")
    assert result.basic_total == D("15")
    assert result.competence_total == D("65")
    assert result.quality_total == D("88")

    political = result.item("moral.political")
    assert (political.raw, political.score) == (D("3"), D("3"))
    assert (political.peer_count, political.peer_trimmed_per_side) == (5, 1)
    assert not political.capped

    morality = result.item("moral.morality")
    assert (morality.raw, morality.score, morality.capped) == (D("12"), D("10"), True)

    second = result.item("basic.second_classroom")
    assert (second.raw, second.score, second.capped) == (D("10.0"), D("5"), True)
    service = result.item("basic.public_service")
    assert (service.raw, service.score, service.capped) == (D("6.0"), D("5"), True)
    fitness = result.item("basic.fitness_test")
    assert (fitness.raw, fitness.score) == (D("59"), D("0"))
    dorm = result.item("basic.dorm_check")
    assert (dorm.raw, dorm.score) == (D("60"), D("5"))
    ability = result.item("ability")
    assert (ability.raw, ability.score, ability.capped) == (D("60"), D("50"), True)

    assert [i.rule_id for i in result.items] == [
        "academic",
        "moral.political",
        "moral.morality",
        "moral.discipline",
        "moral.integrity",
        "moral",
        "basic.second_classroom",
        "basic.public_service",
        "basic.fitness_test",
        "basic.dorm_check",
        "ability",
        "competence",
        "quality",
        "final",
    ]


def test_empty_input_scores_zero(rules: RuleSet) -> None:
    result = calculate(ScoreInput(), rules)
    assert str(result.final_score) == "0.0000"
    assert result.gpa == D("0")
    assert result.quality_total == result.moral_total == result.competence_total == D("0")
    assert result.item("moral.political").raw is None
    assert result.item("basic.fitness_test").raw is None
    assert not any(i.capped or i.floored for i in result.items)


def test_direct_quality_mode(rules: RuleSet) -> None:
    result = calculate(
        ScoreInput(quality_mode="direct", quality_direct=D("120"), gpa=D("3"), ability=D("50")),
        rules,
    )
    assert result.quality_total == D("100")
    assert result.item("quality.direct").capped
    assert result.moral_total is None
    assert result.competence_total is None
    assert result.basic_total is None
    assert [i.rule_id for i in result.items] == ["academic", "quality.direct", "final"]
    assert str(result.final_score) == "3.5000"  # 100 ÷ 20 × 25% + 3 × 75%


def test_direct_quality_mode_empty(rules: RuleSet) -> None:
    result = calculate(ScoreInput(quality_mode="direct"), rules)
    assert result.quality_total == D("0")


def test_negative_basic_input_is_floored_by_competence(rules: RuleSet) -> None:
    # legacy 的第二课堂只有上限没有下限（docs/rules-issues.md R-007）
    result = calculate(ScoreInput(second_classroom=D("-4")), rules)
    assert result.item("basic.second_classroom").score == D("-2.0")
    assert result.basic_total == D("-2.0")
    competence = result.item("competence")
    assert (competence.raw, competence.score, competence.floored) == (D("-2.0"), D("0"), True)


def test_negative_peer_mean_is_floored(rules: RuleSet) -> None:
    result = calculate(ScoreInput(political=_ratings("-3", "-1")), rules)
    item = result.item("moral.political")
    assert (item.raw, item.score, item.floored) == (D("-2"), D("0"), True)


def test_empty_peer_list_scores_zero(rules: RuleSet) -> None:
    result = calculate(ScoreInput(political=PeerRatings(())), rules)
    item = result.item("moral.political")
    assert (item.raw, item.score, item.peer_count) == (D("0"), D("0"), 0)


def test_negative_zero_gpa_is_normalised(rules: RuleSet) -> None:
    result = calculate(ScoreInput(gpa=D("-0")), rules)
    assert str(result.gpa) == "0"
    assert str(result.final_score) == "0.0000"


def test_unrounded_gpa_kept_until_final(rules: RuleSet) -> None:
    # 中间值不舍入，只对最终结果舍入（CLAUDE.md §4.1）
    result = calculate(ScoreInput(gpa=D("3.00006")), rules)
    assert result.final_score_raw == D("2.250045")
    assert str(result.final_score) == "2.2500"


def test_item_lookup_unknown_id(rules: RuleSet) -> None:
    result = calculate(ScoreInput(), rules)
    with pytest.raises(KeyError):
        result.item("no.such.rule")


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"gpa": 3.5}, TypeError),  # 禁止 float
        ({"ability": 1}, TypeError),
        ({"gpa": D("NaN")}, ValueError),
        ({"fitness_test": D("Infinity")}, ValueError),
        ({"political": [D("9")]}, TypeError),  # 评议名单必须用 PeerRatings
        ({"quality_mode": "total"}, ValueError),
    ],
)
def test_score_input_validation(kwargs: dict[str, object], error: type[Exception]) -> None:
    with pytest.raises(error):
        ScoreInput(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("values", "error"),
    [
        ([D("9")], TypeError),  # 必须是 tuple
        ((D("9"), 8.5), TypeError),
        ((D("9"), D("NaN")), ValueError),
    ],
)
def test_peer_ratings_validation(values: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        PeerRatings(values)  # type: ignore[arg-type]


def test_exact_half_rounds_up_unlike_legacy_float(rules: RuleSet) -> None:
    # 4.6278 × 0.75 = 3.47085，恰在 .5 舍入边界：按四舍五入应为 3.4709。
    # legacy 的二进制浮点得到 3.4708（docs/adr/0002-精确十进制舍入.md、rules-issues R-008）
    result = calculate(ScoreInput(quality_mode="direct", gpa=D("4.6278")), rules)
    assert result.final_score_raw == D("3.47085")
    assert str(result.final_score) == "3.4709"


def test_intermediate_rounding_variant(rules: RuleSet) -> None:
    # R-005 备选口径：各项中间值也舍入到 4 位。v1（legacy）只舍入最终结果
    variant = replace(rules, final=replace(rules.final, intermediate_decimal_places=4))
    score_input = ScoreInput(
        gpa=D("4.0"),
        political=PeerRatings((D("1"), D("2"), D("2"))),  # 去极值平均 5/3
        second_classroom=D("2.0025"),  # × 0.5 = 1.00125
    )
    exact = calculate(score_input, rules)
    assert exact.item("moral.political").score.quantize(D("1e-10")) == D("1.6666666667")
    assert exact.quality_total.quantize(D("1e-10")) == D("2.6679166667")  # 5/3 + 1.00125
    assert str(exact.final_score) == "3.0333"  # 3.033348958…

    rounded = calculate(score_input, variant)
    assert rounded.gpa == D("4.0000")
    assert rounded.item("moral.political").score == D("1.6667")
    assert rounded.item("basic.second_classroom").score == D("1.0013")
    assert rounded.quality_total == D("2.6680")
    assert rounded.final_score_raw == D("3.033350")
    assert str(rounded.final_score) == "3.0334"

    direct = calculate(
        ScoreInput(quality_mode="direct", gpa=D("3.12345"), quality_direct=D("80.00005")), variant
    )
    assert (direct.gpa, direct.quality_total) == (D("3.1235"), D("80.0001"))
