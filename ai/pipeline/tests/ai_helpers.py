"""AI 流水线测试辅助：真实的申报目录（规则文件），合成的名单。"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG = json.loads(
    (REPO_ROOT / "rules" / "ability-catalog-xxgc-2020.json").read_text(encoding="utf-8")
)


def options(item_code: str) -> list[tuple[str, str]]:
    item = next(i for i in CATALOG["items"] if i["code"] == item_code)
    return [(o["code"], o["name"]) for o in item.get("options", [])]
