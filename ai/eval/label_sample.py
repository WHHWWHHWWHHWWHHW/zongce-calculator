"""人工抽样核对：计算真实名单的识别与匹配准确率（CLAUDE.md §8 M4、申报书指标 ≥ 95%）。

两步：

    # 1. 从脱敏后的名单中抽样，生成待标注表（只含代号，不含真实姓名）
    uv run python ai/eval/label_sample.py sample real_data/<学年>/脱敏 \\
        real_data/<学年>/标注/抽样.csv --n 300

    # 2. 负责人对照原始文件逐行填写“人工”几列后，计算准确率
    uv run python ai/eval/label_sample.py score real_data/<学年>/标注/抽样.csv \\
        [--report docs/reports/...md]

标注说明（每行一个名单条目，“系统”几列是程序解析的结果）：
- 人工_姓名、人工_班级、人工_分值：系统结果正确填“对”，错误填“错”；原文没有该项填“无”。
- 人工_选项：填正确的申报选项编码（如 college_1；按次计分的参与分填“按次”；无法确定填“无”）。
- 漏识别：原文这一行还有系统没列出的人，在“人工_漏掉人数”填人数。
准确率只按填了“对/错”的格计算；报告中的数字全部来自本脚本输出。
"""

import argparse
import csv
import json
import random
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from zongce_ai.activity_lists import choose_item, parse_activity_list
from zongce_ai.names import majors_from

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "rules" / "ability-catalog-xxgc-2020.json"
SAFE_ROOTS = ("real_data", "data")
SYSTEM = [
    "样本", "文件", "行号", "原文（脱敏）", "系统_活动", "系统_等级", "系统_分值", "系统_班级",
    "系统_姓名", "系统_选项",
]  # fmt: skip
HUMAN = ["人工_姓名", "人工_班级", "人工_分值", "人工_选项", "人工_漏掉人数", "备注"]
FIELDS = ("姓名", "班级", "分值")


def _items(catalog: dict[str, Any]) -> list[tuple[str, list[tuple[str, str, str]], str | None]]:
    items = []
    for code in ("campus_culture_award", "campus_participation"):
        item = next(i for i in catalog["items"] if i["code"] == code)
        options = [(o["code"], o["name"], o["score"]) for o in item.get("options", [])]
        items.append((code, options, item.get("unit_score")))
    return items


def sample(folder: Path, n: int, seed: int) -> list[dict[str, str]]:
    """按文件分层抽样：每个文件按条目数比例分配名额，至少 1 条。"""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = _items(catalog)
    documents = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.rglob("*.json"))]
    classes = [
        row[header.index("班级")]
        for doc in documents
        for table in doc["tables"]
        if table and "班级" in (header := [c.replace(" ", "") for c in table[0]])
        for row in table[1:]
        if header.index("班级") < len(row)
    ]
    majors = majors_from(classes)
    pools: list[tuple[str, list[str], list[Any]]] = []
    for doc in documents:
        parsed = parse_activity_list(doc["text"], majors)
        entries = [e for e in parsed.entries if e.activity]
        if parsed.activities and entries:
            pools.append((doc["source"], doc["text"].splitlines(), entries))
    total = sum(len(p[2]) for p in pools)
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    for source, lines, entries in pools:
        quota = max(1, round(n * len(entries) / total)) if total else 0
        for entry in rng.sample(entries, min(quota, len(entries))):
            choice = choose_item(entry, items)
            option = (
                ""
                if choice is None
                else (choice.option_code or ("按次" if choice.reason == "按次计分" else ""))
            )
            rows.append(
                {
                    "文件": source,
                    "行号": str(entry.line),
                    "原文（脱敏）": lines[entry.line - 1] if entry.line <= len(lines) else "",
                    "系统_活动": entry.activity,
                    "系统_等级": entry.level,
                    "系统_分值": "" if entry.points is None else format(entry.points, "f"),
                    "系统_班级": entry.class_code or "",
                    "系统_姓名": entry.name,
                    "系统_选项": option,
                }
            )
    rng.shuffle(rows)
    for i, row in enumerate(rows, start=1):
        row["样本"] = str(i)
    return rows


REAL_NAME = "真实姓名（仅本机，核对用）"


def write_csv(rows: list[dict[str, str]], path: Path, mapping: Path | None = None) -> None:
    """mapping 为脱敏对照表时，增加一列真实姓名，方便负责人对照原始文件核对（文件只在本机）。"""
    fields = SYSTEM + HUMAN
    if mapping is not None:
        names = json.loads(mapping.read_text(encoding="utf-8"))["names"]
        back = {pseudo: real for real, pseudo in names.items()}
        rows = [{**row, REAL_NAME: back.get(row["系统_姓名"], "")} for row in rows]
        fields = [*SYSTEM, REAL_NAME, *HUMAN]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({**dict.fromkeys(HUMAN, ""), **row})


def score(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    result: dict[str, Any] = {"samples": len(rows)}
    labelled = 0
    for field in FIELDS:
        marks = Counter(r.get(f"人工_{field}", "").strip() for r in rows)
        right, wrong = marks["对"], marks["错"]
        result[field] = {"correct": right, "wrong": wrong, "accuracy": _ratio(right, right + wrong)}
        labelled = max(labelled, right + wrong)
    options = [(r["系统_选项"].strip(), r.get("人工_选项", "").strip()) for r in rows]
    judged = [(s, h) for s, h in options if h]
    right = sum(1 for s, h in judged if s == h or (h == "无" and not s))
    result["选项"] = {
        "correct": right,
        "wrong": len(judged) - right,
        "accuracy": _ratio(right, len(judged)),
    }
    missed = sum(int(r.get("人工_漏掉人数", "") or 0) for r in rows)
    result["漏识别人数"] = missed
    entries = len(rows)
    result["召回率（条目）"] = _ratio(entries, entries + missed)
    result["labelled"] = max(labelled, len(judged))
    return result


def _ratio(part: int, whole: int) -> str | None:
    return None if whole == 0 else f"{part * 100 / whole:.1f}%"


def render(result: dict[str, Any], *, day: str) -> str:
    lines = [
        f"# 真实名单人工抽样核对（{day}）",
        "",
        f"- 样本：{result['samples']} 条（按文件分层随机抽样，数据已脱敏，明细不入库）。",
        "- 生成命令：`uv run python ai/eval/label_sample.py score <标注表> --report <本文件>`。",
        "",
        "| 项目 | 对 | 错 | 准确率 |",
        "|---|---:|---:|---:|",
    ]
    for field in (*FIELDS, "选项"):
        r = result[field]
        lines.append(f"| {field} | {r['correct']} | {r['wrong']} | {r['accuracy'] or '—'} |")
    lines += [
        "",
        f"漏识别人数（原文有、系统没列出）：{result['漏识别人数']}；"
        f"按条目计的召回率：{result['召回率（条目）'] or '—'}。",
        "",
    ]
    return "\n".join(lines)


def _check_safe(path: Path) -> None:
    if not any(part in SAFE_ROOTS for part in path.resolve().parts):
        raise SystemExit(f"{path} 不在 real_data/ 或 data/ 下；抽样表不能放在会被提交的位置")


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sample")
    s.add_argument("desensitized", type=Path)
    s.add_argument("output", type=Path)
    s.add_argument("--n", type=int, default=300)
    s.add_argument("--seed", type=int, default=20261021)
    s.add_argument(
        "--mapping", type=Path, help="脱敏对照表；给出时增加一列真实姓名（只在本机核对用）"
    )
    c = sub.add_parser("score")
    c.add_argument("labelled", type=Path)
    c.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.command == "sample":
        _check_safe(args.output)
        rows = sample(args.desensitized, args.n, args.seed)
        write_csv(rows, args.output, args.mapping)
        summary: dict[str, Any] = {"samples": len(rows), "output": str(args.output)}
    else:
        summary = score(args.labelled)
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(render(summary, day=date.today().isoformat()), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return summary


if __name__ == "__main__":
    main()
