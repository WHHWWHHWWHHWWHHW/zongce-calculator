"""在脱敏后的真实表单上评测“活动获奖名单”的解析与学生匹配（只输出统计，CLAUDE.md §11）。

    uv run python ai/eval/real_forms.py real_data/<学年>/脱敏 \\
        [--report docs/reports/real-forms-YYYYMMDD.md]

输入是 ai/eval/desensitize.py 的输出。没有人工标注，所以这里给出的是可以直接核对的量：
- 解析：识别出的活动、名单条目，以及还有没认出内容的行数；
- 匹配：用表单里自带的名册（含“姓名”“班级”列的表，如到梦空间学分、志愿章汇总）
  按“班级 + 姓名”或只按姓名找学生，统计唯一找到、找到多人（重名）、找不到的条目数；
- 对应申报目录：按分值与等级能确定申报选项的条目数。
"""

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from zongce_ai.activity_lists import choose_item, parse_activity_list
from zongce_ai.names import majors_from, normalize_class

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "rules" / "ability-catalog-xxgc-2020.json"
ACTIVITY_ITEMS = ("campus_culture_award", "campus_participation")
# 同一专业在不同表里的写法（名册写“人工智能2503”，名单写“智能 2503”）
MAJOR_ALIASES = {"人工智能": "智能"}


def _class_key(code: str) -> str:
    for long, short in MAJOR_ALIASES.items():
        if code.startswith(long):
            return short + code[len(long) :]
    return code


def roster_from(documents: list[dict[str, Any]]) -> dict[str, set[str]]:
    """名册：姓名 → 班级集合。取自同时有“姓名”和“班级”列的表格。"""
    roster: dict[str, set[str]] = {}
    for doc in documents:
        for table in doc["tables"]:
            if not table:
                continue
            header = [c.replace(" ", "") for c in table[0]]
            if "姓名" not in header or "班级" not in header:
                continue
            name_col, class_col = header.index("姓名"), header.index("班级")
            for row in table[1:]:
                if max(name_col, class_col) < len(row) and row[name_col]:
                    code = normalize_class(row[class_col]) or row[class_col]
                    roster.setdefault(row[name_col], set()).add(_class_key(code))
    return roster


def _items(catalog: dict[str, Any]) -> list[tuple[str, list[tuple[str, str, str]], str | None]]:
    items = []
    for code in ACTIVITY_ITEMS:
        item = next(i for i in catalog["items"] if i["code"] == code)
        options = [(o["code"], o["name"], o["score"]) for o in item.get("options", [])]
        items.append((code, options, item.get("unit_score")))
    return items


def evaluate(documents: list[dict[str, Any]], catalog: dict[str, Any]) -> dict[str, Any]:
    roster = roster_from(documents)
    majors = majors_from(c for classes in roster.values() for c in classes)
    items = _items(catalog)
    stats: Counter[str] = Counter()
    options: Counter[str] = Counter()
    for doc in documents:
        parsed = parse_activity_list(doc["text"], majors)
        if not parsed.entries:
            continue
        stats["documents"] += 1
        stats["activities"] += parsed.activities
        stats["entries"] += len(parsed.entries)
        stats["partial_lines"] += len(parsed.partial_lines)
        for entry in parsed.entries:
            classes = roster.get(entry.name, set())
            if entry.class_code is not None:
                stats["entries_with_class"] += 1
            if entry.class_code is not None and _class_key(entry.class_code) in classes:
                stats["matched_by_class_and_name"] += 1
            elif len(classes) == 1:
                stats["matched_by_name_only"] += 1
            elif len(classes) > 1:
                stats["ambiguous_same_name"] += 1
            else:
                stats["not_in_roster"] += 1
            if entry.points is not None:
                stats["entries_with_points"] += 1
            choice = choose_item(entry, items)
            if choice is not None and (choice.option_code or choice.reason == "按次计分"):
                stats["mapped_to_catalog"] += 1
                options[f"{choice.item_code}.{choice.option_code or '按次'}"] += 1
    return {
        "roster_names": len(roster),
        **{k: stats[k] for k in (
            "documents", "activities", "entries", "partial_lines", "entries_with_class",
            "matched_by_class_and_name", "matched_by_name_only", "ambiguous_same_name",
            "not_in_roster", "entries_with_points", "mapped_to_catalog",
        )},
        "options": dict(options.most_common()),
    }  # fmt: skip


def _pct(part: int, whole: int) -> str:
    return "—" if whole == 0 else f"{part * 100 / whole:.1f}%"


def render_report(s: dict[str, Any], *, source: str, day: str) -> str:
    n = s["entries"]
    lines = [
        f"# 真实表单解析与匹配统计（{day}）",
        "",
        f"- 数据：{source}，已在本机脱敏（`ai/eval/desensitize.py`），明细不入库；本报告只含计数。",
        "- 范围：学院各部门的“活动获奖名单”（团委、学习部、文艺部、管服、资助心协等）。",
        "- 生成命令：`uv run python ai/eval/real_forms.py <脱敏目录> --report <本文件>`。",
        "- 说明：没有人工标注，以下不是“准确率”，而是解析覆盖与能否在名册中找到学生的统计。",
        "",
        "| 指标 | 数量 | 占名单条目 |",
        "|---|---:|---:|",
        f"| 名单文件 | {s['documents']} | |",
        f"| 活动 | {s['activities']} | |",
        f"| 名单条目（人次） | {n} | {_pct(n, n)} |",
        f"| 带班级的条目 | {s['entries_with_class']} | {_pct(s['entries_with_class'], n)} |",
        f"| 按“班级 + 姓名”在名册中找到 | {s['matched_by_class_and_name']} "
        f"| {_pct(s['matched_by_class_and_name'], n)} |",
        f"| 只按姓名唯一找到 | {s['matched_by_name_only']} "
        f"| {_pct(s['matched_by_name_only'], n)} |",
        f"| 重名（名册中有多人） | {s['ambiguous_same_name']} "
        f"| {_pct(s['ambiguous_same_name'], n)} |",
        f"| 名册中没有 | {s['not_in_roster']} | {_pct(s['not_in_roster'], n)} |",
        f"| 名单给出分值 | {s['entries_with_points']} | {_pct(s['entries_with_points'], n)} |",
        f"| 能确定申报目录选项 | {s['mapped_to_catalog']} | {_pct(s['mapped_to_catalog'], n)} |",
        f"| 还有没认出内容的行 | {s['partial_lines']} | |",
        "",
        f"名册（含“姓名”“班级”列的表）共 {s['roster_names']} 个不同姓名。",
        "",
        "对应到的申报选项："
        + ("，".join(f"`{k}` {v}" for k, v in s["options"].items()) or "无")
        + "。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("desensitized", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--source", default="2025–2026 学年学院各部门综测汇总（负责人提供）")
    args = parser.parse_args(argv)
    documents = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.desensitized.rglob("*.json"))
    ]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    summary = evaluate(documents, catalog)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            render_report(summary, source=args.source, day=date.today().isoformat()),
            encoding="utf-8",
        )
    return summary


if __name__ == "__main__":
    main()
