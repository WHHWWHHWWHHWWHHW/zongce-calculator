"""外发前脱敏（CLAUDE.md §11）：学号做带密钥的哈希，姓名换成占位符；日志只记录哈希。"""

import hashlib
import hmac


class Pseudonymizer:
    """同一个密钥下，同一学号总是得到同一个代号，可以还原（只在本机保存对照表）。"""

    def __init__(self, secret: bytes) -> None:
        if len(secret) < 16:
            raise ValueError("脱敏密钥至少 16 字节")
        self._secret = secret
        self._back: dict[str, str] = {}
        self._names: dict[str, str] = {}

    def student(self, student_id: str) -> str:
        token = "S" + hmac.new(self._secret, student_id.encode(), hashlib.sha256).hexdigest()[:12]
        self._back[token] = student_id
        return token

    def name(self, name: str) -> str:
        return self._names.setdefault(name, f"学生{len(self._names) + 1}")

    def restore(self, token: str) -> str:
        return self._back[token]


def log_digest(text: str) -> str:
    """外发内容写日志时只记录这个摘要，不记录明文。"""
    return hashlib.sha256(text.encode()).hexdigest()
