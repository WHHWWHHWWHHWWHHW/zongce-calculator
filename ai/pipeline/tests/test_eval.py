"""评测脚本 ai/eval/evaluate.py：指标计算与报告。"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from ai_helpers import CATALOG, REPO_ROOT

SCRIPT = REPO_ROOT / "ai" / "eval" / "evaluate.py"
DATASET = REPO_ROOT / "ai" / "eval" / "datasets" / "award-lists-synthetic.json"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evaluate", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case(rows: list[list[str]], truth: list[dict[str, object]]) -> dict[str, object]:
    return {
        "cases": [
            {
                "catalog_item": "december_ninth_run",
                "context": "",
                "rows": rows,
                "students": [
                    {"student_id": "TEST1", "name": "甲"},
                    {"student_id": "TEST2", "name": "乙"},
                ],
                "declarations": [
                    {"id": 1, "student_id": "TEST1", "option_code": "first"},
                    {"id": 2, "student_id": "TEST2", "option_code": "second"},
                ],
                "truth": truth,
            }
        ]
    }


def test_metrics_count_errors() -> None:
    evaluate = _load()
    rows = [
        ["学号", "姓名", "等级"],
        ["TEST1", "甲", "一等奖"],
        ["TEST2", "乙", "二等奖"],
        ["", "", ""],
    ]
    truth = [
        {"row": 2, "student_id": "TEST1", "option_code": "first", "fast_track": False},  # 误放行
        {"row": 3, "student_id": "TEST2", "option_code": "third", "fast_track": True},
        {"row": 4, "student_id": "TEST3", "option_code": "first", "fast_track": True},  # 被跳过
    ]
    summary = evaluate.evaluate(_case(rows, truth), CATALOG).summary()
    assert (summary["rows"], summary["student_id_correct"], summary["option_correct"]) == (3, 2, 1)
    assert (summary["true_positive"], summary["false_positive"], summary["false_negative"]) == (
        1,
        1,
        1,
    )
    assert summary["fast_track_precision"] == "0.5000"
    assert summary["fast_track_recall"] == "0.5000"
    assert summary["routes"] == {"fast_track": 2, "manual": 0, "info": 0}


def test_empty_dataset_has_no_ratios() -> None:
    summary = _load().evaluate({"cases": []}, CATALOG).summary()
    assert summary["option_accuracy"] is None
    assert summary["fast_track_precision"] is None


def test_main_on_committed_synthetic_dataset(tmp_path: Path) -> None:
    report = tmp_path / "ai-eval.md"
    summary = _load().main([str(DATASET), "--report", str(report), "--date", "2026-10-20"])
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    assert summary["rows"] == sum(len(c["truth"]) for c in data["cases"])
    assert summary["false_positive"] == 0  # 合成集上不应误放行
    text = report.read_text(encoding="utf-8")
    assert "合成数据（不代表真实表单上的准确率）" in text
    assert "TEST" not in text
    assert "| 可快速通过·精确率 | 100.00%" in text


def test_report_for_desensitized_data() -> None:
    evaluate = _load()
    summary = evaluate.evaluate({"cases": []}, CATALOG).summary()
    text = evaluate.render_report(summary, dataset="x.json", synthetic=False, date="d")
    assert "已脱敏数据" in text
    assert "| 学号识别准确率 | —" in text
