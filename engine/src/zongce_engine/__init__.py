"""综测计分规则引擎：纯 Python、Decimal 计算、不做 IO（CLAUDE.md §6）。"""

from .calculator import calculate
from .models import ItemResult, MoralValue, PeerRatings, QualityMode, ScoreInput, ScoreResult
from .numbers import format_score
from .parsing import NonFiniteInputError, extract_numbers, parse_rating_text
from .rules import RuleError, RuleSet

__all__ = [
    "ItemResult",
    "MoralValue",
    "NonFiniteInputError",
    "PeerRatings",
    "QualityMode",
    "RuleError",
    "RuleSet",
    "ScoreInput",
    "ScoreResult",
    "calculate",
    "extract_numbers",
    "format_score",
    "parse_rating_text",
]
