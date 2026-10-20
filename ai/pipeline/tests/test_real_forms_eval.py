"""ai/eval/real_forms.py：在（虚构的）脱敏数据上统计解析与匹配。"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from ai_helpers import CATALOG, REPO_ROOT


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "real_forms", REPO_ROOT / "ai" / "eval" / "real_forms.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROSTER = {
    "source": "名册.xlsx",
    "tables": [
        [
            ["姓名", "学号", "班级"],
            ["学生0001", "1", "人工智能2501"],
            ["学生0002", "2", "计科2501"],
            ["学生0003", "3", "计科2501"],
            ["学生0003", "4", "网安2401"],  # 重名
        ],
        [],
        [["班级", "备注"], ["计科2501", "x"]],  # 没有姓名列，不是名册
    ],
    "text": "",
}
LIST = {
    "source": "团委.pdf",
    "tables": [],
    "text": "活动名称：某活动\n一等奖：2 分\n智能 2501 学生0001 网合25W3 学生0002\n"
    "二等奖：1.5 分\n学生0003 学生0009\n工作人员：0.2 分\n学生0002 学生0001 某某某某某某\n"
    "三等奖\n学生0001 学生0002\n",
}


def test_evaluate_counts() -> None:
    summary = _load().evaluate(
        [ROSTER, LIST, {"source": "空", "tables": [], "text": "无"}], CATALOG
    )
    assert summary["roster_names"] == 3
    assert (summary["documents"], summary["activities"], summary["entries"]) == (1, 1, 8)
    assert summary["entries_with_class"] == 2
    assert summary["matched_by_class_and_name"] == 1  # 智能2501 = 人工智能2501
    assert summary["matched_by_name_only"] == 5  # 学生0002（班级不符）以及只有姓名的条目
    assert summary["ambiguous_same_name"] == 1
    assert summary["not_in_roster"] == 1  # 学生0009
    assert summary["partial_lines"] == 1
    assert summary["entries_with_points"] == 6  # “三等奖”没写分值
    assert summary["mapped_to_catalog"] == 6
    assert summary["options"]["campus_participation.按次"] == 2


def test_main_writes_report(tmp_path: Path) -> None:
    folder = tmp_path / "脱敏"
    folder.mkdir()
    (folder / "名册.json").write_text(json.dumps(ROSTER, ensure_ascii=False), encoding="utf-8")
    (folder / "团委.json").write_text(json.dumps(LIST, ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.md"
    _load().main([str(folder), "--report", str(report)])
    text = report.read_text(encoding="utf-8")
    assert "| 名单条目（人次） | 8 | 100.0% |" in text
    assert "学生0001" not in text  # 报告只含计数
    keys = (
        "documents", "activities", "entries", "partial_lines", "entries_with_class",
        "matched_by_class_and_name", "matched_by_name_only", "ambiguous_same_name",
        "not_in_roster", "entries_with_points", "mapped_to_catalog", "roster_names",
    )  # fmt: skip
    empty = _load().render_report(dict.fromkeys(keys, 0) | {"options": {}}, source="x", day="d")
    assert "| 名单条目（人次） | 0 | — |" in empty
    assert "对应到的申报选项：无。" in empty
