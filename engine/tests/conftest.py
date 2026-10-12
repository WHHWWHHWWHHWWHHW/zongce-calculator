"""引擎单元测试的公共夹具。"""

import json
from pathlib import Path
from typing import Any

import pytest

from zongce_engine import RuleSet

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_V1 = REPO_ROOT / "rules" / "ujn-v1.json"
SCHEMA = REPO_ROOT / "rules" / "schema.json"


@pytest.fixture
def rules_path() -> Path:
    return RULES_V1


@pytest.fixture
def rules_data() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(RULES_V1.read_text(encoding="utf-8"))
    return data


@pytest.fixture
def schema_data() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return data


@pytest.fixture
def rules(rules_data: dict[str, Any]) -> RuleSet:
    return RuleSet.from_dict(rules_data)
