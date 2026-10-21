"""ai/eval/label_sample.py：抽样生成待标注表、按标注计算准确率（虚构数据）。"""

import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from ai_helpers import REPO_ROOT


def _load() -> ModuleType:
    path = REPO_ROOT / "ai" / "eval" / "label_sample.py"
    spec = importlib.util.spec_from_file_location("label_sample", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROSTER = {
    "source": "名册.xlsx",
    "tables": [[["姓名", "班级"], ["学生0001", "计科2501"]]],
    "text": "",
}
LIST = {
    "source": "团委.pdf",
    "tables": [],
    "text": "活动名称：某活动\n一等奖：2 分\n计科2501 学生0001 计科2501 学生0002\n"
    "工作人员：0.2 分\n学生0003 学生0004\n三等奖\n学生0005 学生0006\n",
}
OTHER = {
    "source": "学习部.pdf",
    "tables": [],
    "text": "活动名称：辩论赛\n第一名：2 分\n学生0007 学生0008\n",
}


def _folder(tmp_path: Path) -> Path:
    folder = tmp_path / "real_data" / "脱敏"
    folder.mkdir(parents=True)
    for i, doc in enumerate((ROSTER, LIST, OTHER, {"source": "空", "tables": [[]], "text": ""})):
        (folder / f"{i}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return folder


def test_sample_then_score(tmp_path: Path) -> None:
    module = _load()
    out = tmp_path / "real_data" / "标注" / "抽样.csv"
    summary = module.main(["sample", str(_folder(tmp_path)), str(out), "--n", "8"])
    assert summary["samples"] == 8  # 名额按条目数分配，这里正好全部抽到
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["样本"] for r in rows] == [str(i) for i in range(1, 9)]
    assert {r["文件"] for r in rows} == {"团委.pdf", "学习部.pdf"}
    by_name = {r["系统_姓名"]: r for r in rows}
    assert by_name["学生0001"]["系统_选项"] == "college_1"
    assert by_name["学生0001"]["原文（脱敏）"].startswith("计科2501 学生0001")
    assert by_name["学生0003"]["系统_选项"] == "按次"
    assert by_name["学生0005"]["系统_分值"] == ""  # 三等奖没写分值

    for r in rows:  # 模拟人工标注：一条姓名错、一条选项改判、一行漏了 1 人
        r["人工_姓名"] = "对"
        r["人工_班级"] = "对" if r["系统_班级"] else "无"
        r["人工_分值"] = "对" if r["系统_分值"] else "无"
        r["人工_选项"] = r["系统_选项"] or "无"
    rows[0]["人工_姓名"] = "错"
    by_name["学生0001"]["人工_选项"] = "university_3"
    rows[1]["人工_漏掉人数"] = "1"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = tmp_path / "report.md"
    result = module.main(["score", str(out), "--report", str(report)])
    assert result["姓名"] == {"correct": 7, "wrong": 1, "accuracy": "87.5%"}
    assert result["选项"]["wrong"] == 1
    assert result["漏识别人数"] == 1
    assert result["召回率（条目）"] == "88.9%"
    text = report.read_text(encoding="utf-8")
    assert "| 姓名 | 7 | 1 | 87.5% |" in text
    assert "学生0001" not in text


def test_sample_with_real_names_for_local_checking(tmp_path: Path) -> None:
    module = _load()
    mapping = tmp_path / "real_data" / "私密" / "对照表.json"
    mapping.parent.mkdir(parents=True)
    names = {"张三": "学生0001", "李四": "学生0002"}
    mapping.write_text(json.dumps({"names": names, "ids": {}}), encoding="utf-8")
    out = tmp_path / "real_data" / "标注" / "核对.csv"
    module.main(["sample", str(_folder(tmp_path)), str(out), "--n", "8", "--mapping", str(mapping)])
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = {r["系统_姓名"]: r for r in csv.DictReader(f)}
    assert rows["学生0001"][module.REAL_NAME] == "张三"
    assert rows["学生0005"][module.REAL_NAME] == ""


def test_empty_and_unsafe(tmp_path: Path) -> None:
    module = _load()
    empty = tmp_path / "real_data" / "空"
    empty.mkdir(parents=True)
    assert module.sample(empty, 10, 1) == []
    blank = tmp_path / "real_data" / "空.csv"
    module.write_csv([], blank)
    result = module.score(blank)
    assert result["姓名"]["accuracy"] is None
    assert "| 选项 | 0 | 0 | — |" in module.render(result, day="d")
    with pytest.raises(SystemExit, match="real_data"):
        module.main(["sample", str(empty), str(tmp_path / "out.csv")])
