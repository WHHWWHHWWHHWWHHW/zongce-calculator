"""约束检查：引擎源码中不出现 float，不做 IO（CLAUDE.md §6、§10）。"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "zongce_engine"
SOURCES = sorted(SRC.rglob("*.py"))
FORBIDDEN_MODULES = {
    "io",
    "os",
    "sys",
    "pathlib",
    "json",
    "shutil",
    "socket",
    "subprocess",
    "tempfile",
    "urllib",
    "http",
    "requests",
    "random",
    "time",
    "datetime",
}
FORBIDDEN_NAMES = {"float", "open", "print", "input", "eval", "exec"}


def test_sources_found() -> None:
    assert len(SOURCES) >= 5


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_float_and_no_io(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        where = f"{path.name}:{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.Constant):
            assert not isinstance(node.value, float | complex), f"{where} 出现浮点字面量"
        elif isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_NAMES, f"{where} 使用了 {node.id}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in FORBIDDEN_MODULES, (
                    f"{where} 导入 {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            assert module not in FORBIDDEN_MODULES, f"{where} 导入 {node.module}"
