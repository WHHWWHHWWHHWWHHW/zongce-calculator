"""AI 提供方（CLAUDE.md §8 M4）：AI_PROVIDER=none|local|remote，默认 none。

- none：只解析 Excel / CSV 表格；图片和扫描件明确报错，平台其余功能完整可用。
- local / remote：OCR + 大模型抽取，尚未接入（需要负责人确定模型与密钥，CLAUDE.md §13 第 4 项）。
  remote 外发前必须脱敏（privacy.py），外发内容只记录哈希。
"""

from enum import StrEnum
from typing import Protocol

from .models import ExtractedRecord


class AiProvider(StrEnum):
    NONE = "none"
    LOCAL = "local"
    REMOTE = "remote"


class AiDisabledError(RuntimeError):
    """AI_PROVIDER=none 时请求了需要 AI 的功能。"""


class AiUnavailableError(RuntimeError):
    """配置了 local / remote，但对应的识别服务尚未接入。"""


class ImageExtractor(Protocol):
    def extract(self, data: bytes, content_type: str) -> list[ExtractedRecord]: ...


class _Disabled:
    def extract(self, data: bytes, content_type: str) -> list[ExtractedRecord]:
        raise AiDisabledError("未启用 AI 识别（AI_PROVIDER=none），请上传 Excel 或 CSV 表格")


class _NotConnected:
    def __init__(self, provider: AiProvider) -> None:
        self.provider = provider

    def extract(self, data: bytes, content_type: str) -> list[ExtractedRecord]:
        raise AiUnavailableError(f"AI_PROVIDER={self.provider.value} 的识别服务尚未接入")


def image_extractor(provider: AiProvider) -> ImageExtractor:
    if provider is AiProvider.NONE:
        return _Disabled()
    return _NotConnected(provider)
