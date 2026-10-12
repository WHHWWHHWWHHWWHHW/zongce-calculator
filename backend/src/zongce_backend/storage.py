"""证明材料文件存储（先用本地磁盘，接口抽象便于以后换 MinIO，CLAUDE.md §6）。"""

import secrets
from pathlib import Path
from typing import Protocol


class FileStorage(Protocol):
    def save(self, data: bytes, suffix: str) -> str:
        """保存文件，返回随机生成的存储名。"""
        ...

    def load(self, stored_name: str) -> bytes: ...

    def delete(self, stored_name: str) -> None: ...


class LocalFileStorage:
    """按随机名存放在 base_dir 下；不使用用户提供的文件名拼接路径（CLAUDE.md §11）。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def _path(self, stored_name: str) -> Path:
        if not stored_name or "/" in stored_name or "\\" in stored_name or ".." in stored_name:
            raise ValueError("非法的存储名")
        return self.base_dir / stored_name

    def save(self, data: bytes, suffix: str) -> str:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{secrets.token_hex(16)}{suffix}"
        self._path(stored_name).write_bytes(data)
        return stored_name

    def load(self, stored_name: str) -> bytes:
        return self._path(stored_name).read_bytes()

    def delete(self, stored_name: str) -> None:
        self._path(stored_name).unlink(missing_ok=True)
