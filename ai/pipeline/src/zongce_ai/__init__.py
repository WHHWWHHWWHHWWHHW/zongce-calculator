"""AI 辅助审核流水线：表单解析、校验、与申报匹配、按置信度分流。只产生建议，不改分。"""

from .matching import DeclarationRef, MatchReport, MatchStatus, Route, StudentRef, Suggestion, match
from .models import ExtractedRecord, TableExtraction
from .options import OptionMatch, match_option
from .providers import AiDisabledError, AiProvider, AiUnavailableError, image_extractor
from .tables import extract_award_rows

__all__ = [
    "AiDisabledError",
    "AiProvider",
    "AiUnavailableError",
    "DeclarationRef",
    "ExtractedRecord",
    "MatchReport",
    "MatchStatus",
    "OptionMatch",
    "Route",
    "StudentRef",
    "Suggestion",
    "TableExtraction",
    "extract_award_rows",
    "image_extractor",
    "match",
    "match_option",
]
