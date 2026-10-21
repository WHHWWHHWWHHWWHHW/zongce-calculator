"""AI_PROVIDER 与外发前脱敏。"""

import pytest

from zongce_ai import AiDisabledError, AiProvider, AiUnavailableError, image_extractor
from zongce_ai.privacy import Pseudonymizer, log_digest


def test_none_provider_refuses_images() -> None:
    with pytest.raises(AiDisabledError, match="AI_PROVIDER=none"):
        image_extractor(AiProvider.NONE).extract(b"\x89PNG", "image/png")


@pytest.mark.parametrize("provider", [AiProvider.LOCAL, AiProvider.REMOTE])
def test_other_providers_not_connected_yet(provider: AiProvider) -> None:
    with pytest.raises(AiUnavailableError, match="尚未接入"):
        image_extractor(provider).extract(b"%PDF", "application/pdf")


def test_pseudonymizer() -> None:
    p = Pseudonymizer(b"k" * 16)
    token = p.student("TEST01001")
    assert token != "TEST01001"
    assert token == p.student("TEST01001")  # 稳定
    assert token != Pseudonymizer(b"j" * 16).student("TEST01001")  # 依赖密钥
    assert p.restore(token) == "TEST01001"
    assert (p.name("测试学生甲"), p.name("测试学生乙"), p.name("测试学生甲")) == (
        "学生1", "学生2", "学生1",
    )  # fmt: skip
    assert "TEST01001" not in log_digest("TEST01001 一等奖")
    with pytest.raises(ValueError, match="16 字节"):
        Pseudonymizer(b"short")
