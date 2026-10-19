"""获奖等级原文 → 申报目录选项。"""

from decimal import Decimal

import pytest

from ai_helpers import options
from zongce_ai import match_option
from zongce_ai.options import ALIAS, AMBIGUOUS, CONFIDENT, LIKELY


@pytest.mark.parametrize(
    ("item", "text", "code", "confidence"),
    [
        ("competition", "一类赛事 省级 一等奖", "c1_provincial_1", CONFIDENT),
        ("competition", "一类 省一", "c1_provincial_1", CONFIDENT),
        ("competition", "一类 省一等奖", "c1_provincial_1", CONFIDENT),
        ("competition", "二类赛事 国家级 银奖", "c2_national_2", CONFIDENT),
        ("competition", "三类赛事 全国 特等奖", "c3_national_1", CONFIDENT),  # 一等奖及以上
        ("competition", "１类 校级 三等", "c1_university_3", CONFIDENT),  # 全角数字
        ("competition", "c2_provincial_3", "c2_provincial_3", Decimal(1)),
        ("volunteer_contest", "省级 金奖", "provincial_1", CONFIDENT),
        ("practice_report", "院级一等奖", "college_a", CONFIDENT),
        ("competition", "一类 省级 优秀奖", "c12_merit", CONFIDENT),  # 省级及以上
        ("competition", "二类 国家级 完成奖", "c12_merit", CONFIDENT),
        ("competition", "院级学科类竞赛 二等奖", "college_2", CONFIDENT),
        ("practice_report", "济南大学 二等奖", "university_2", CONFIDENT),
        ("university_games", "个人项目 第一名", "individual_1", CONFIDENT),
        ("university_games", "接力 第3名", "relay_3", CONFIDENT),
        ("college_games", "个人 第六名", "individual_4_8", CONFIDENT),  # 第四–八名
        ("campus_culture_award", "市级 优秀奖", "provincial_merit", CONFIDENT),  # 省市级
        ("december_ninth_run", "一等奖", "first", CONFIDENT),
        ("ball_games", "男子篮球赛 第二名", "rank_2", CONFIDENT),
        ("dorm_honor", "校级优秀宿舍", "university", CONFIDENT),
        ("competition", "一类 省级 一等奖 团体", "c1_provincial_1", CONFIDENT),
        ("december_ninth_run", "院级 二等奖", "second", LIKELY),  # 原文多了级别
        ("honor_university", "济南大学优秀学生干部", "excellent", ALIAS),
        ("cadre", "担任班长", "minister", ALIAS),
        ("cadre", "院学生组织主席团成员", "presidium", ALIAS),
        ("honor_college", "院级优秀团员", "college", Decimal(1)),  # 只有一个选项
    ],
)
def test_match(item: str, text: str, code: str, confidence: Decimal) -> None:
    result = match_option(text, options(item))
    assert (result.option_code, result.confidence) == (code, confidence), result.reason


@pytest.mark.parametrize(
    ("item", "text", "confidence"),
    [
        ("competition", "省级 一等奖", AMBIGUOUS),  # 缺赛事类别
        ("competition", "参赛", Decimal(0)),
        ("competition", "三类 省级 优秀奖", Decimal(0)),  # 三类赛事没有优秀奖
        ("honor_university", "济南大学十佳团员 济南大学优秀学生", AMBIGUOUS),  # 两个称号
    ],
)
def test_no_guess(item: str, text: str, confidence: Decimal) -> None:
    result = match_option(text, options(item))
    assert result.option_code is None
    assert result.confidence == confidence


def test_alias_does_not_rewrite_honor_names() -> None:
    # “全国三好学生”不能被当成“国家级三等奖”的缩写
    result = match_option("全国三好学生", options("honor_national"))
    assert result.option_code == "national"
