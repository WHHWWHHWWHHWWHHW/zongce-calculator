"""调用 tests/parity/run_legacy.mjs，在 jsdom 中运行 legacy 页面。"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .cases import REPO_ROOT

PARITY_DIR = REPO_ROOT / "tests" / "parity"


def run_legacy(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("对拍需要 Node.js（>= 20）")
    if not (PARITY_DIR / "node_modules" / "jsdom").is_dir():
        raise RuntimeError("缺少 jsdom：请先在 tests/parity 下运行 pnpm install --frozen-lockfile")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cases.json"
        path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [node, str(PARITY_DIR / "run_legacy.mjs"), str(path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"legacy 执行失败：\n{proc.stderr}")
    results: list[dict[str, Any]] = json.loads(proc.stdout)
    return results
