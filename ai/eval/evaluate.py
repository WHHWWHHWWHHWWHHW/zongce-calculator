"""AI 辅助审核评测：字段级准确率、“可快速通过”的精确率与召回率（CLAUDE.md §8 M4）。

报告中的数字必须来自本脚本的输出（CLAUDE.md §3 第 8 条）。评测集只能是合成数据或已脱敏数据。

用法：
    uv run python scripts/gen_fake_data.py --ai-eval ai/eval/datasets/award-lists-synthetic.json
    uv run python ai/eval/evaluate.py ai/eval/datasets/award-lists-synthetic.json \\
        --report docs/reports/ai-eval-YYYYMMDD.md
"""

import argparse
import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from zongce_ai import DeclarationRef, Route, StudentRef, extract_award_rows, match

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "rules" / "ability-catalog-xxgc-2020.json"


@dataclass
class Metrics:
    rows: int = 0
    student_id_correct: int = 0
    option_correct: int = 0
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    routes: dict[str, int] = field(default_factory=lambda: {r.value: 0 for r in Route})

    @staticmethod
    def _ratio(part: int, whole: int) -> str | None:
        return (
            None
            if whole == 0
            else str((Decimal(part) / Decimal(whole)).quantize(Decimal("0.0001")))
        )

    def summary(self) -> dict[str, Any]:
        predicted = self.true_positive + self.false_positive
        actual = self.true_positive + self.false_negative
        return {
            **asdict(self),
            "student_id_accuracy": self._ratio(self.student_id_correct, self.rows),
            "option_accuracy": self._ratio(self.option_correct, self.rows),
            "fast_track_precision": self._ratio(self.true_positive, predicted),
            "fast_track_recall": self._ratio(self.true_positive, actual),
        }


def _options(catalog: dict[str, Any], item_code: str) -> list[tuple[str, str]]:
    item = next(i for i in catalog["items"] if i["code"] == item_code)
    return [(o["code"], o["name"]) for o in item.get("options", [])]


def evaluate(dataset: dict[str, Any], catalog: dict[str, Any]) -> Metrics:
    metrics = Metrics()
    for case in dataset["cases"]:
        extraction = extract_award_rows(
            case["rows"], _options(catalog, case["catalog_item"]), context=case["context"]
        )
        report = match(
            extraction.records,
            [DeclarationRef(**d) for d in case["declarations"]],
            [StudentRef(**s) for s in case["students"]],
        )
        records = {r.row: r for r in extraction.records}
        routes = {s.row: s.route for s in report.suggestions}
        for truth in case["truth"]:
            metrics.rows += 1
            record = records.get(truth["row"])
            if record is not None and record.student_id == truth["student_id"]:
                metrics.student_id_correct += 1
            if record is not None and record.option_code == truth["option_code"]:
                metrics.option_correct += 1
            route = routes.get(truth["row"])
            if route is not None:
                metrics.routes[route.value] += 1
            predicted = route is Route.FAST_TRACK
            if predicted and truth["fast_track"]:
                metrics.true_positive += 1
            elif predicted:
                metrics.false_positive += 1
            elif truth["fast_track"]:
                metrics.false_negative += 1
    return metrics


def _percent(ratio: str | None) -> str:
    return "—" if ratio is None else f"{Decimal(ratio) * 100:.2f}%"


def render_report(summary: dict[str, Any], *, dataset: str, synthetic: bool, date: str) -> str:
    kind = "合成数据（不代表真实表单上的准确率）" if synthetic else "已脱敏数据"
    return "\n".join(
        [
            f"# AI 辅助审核评测（{date}）",
            "",
            f"- 评测集：`{dataset}`，{kind}；共 {summary['rows']} 行名单。",
            "- 方法：表格解析 + 规则匹配（`AI_PROVIDER=none`，未使用 OCR 和大模型），"
            "快速通过阈值 0.9。",
            "- 生成命令：`uv run python ai/eval/evaluate.py <评测集> --report <本文件>`。",
            "",
            "| 指标 | 结果 |",
            "|---|---:|",
            f"| 学号识别准确率 | {_percent(summary['student_id_accuracy'])}"
            f"（{summary['student_id_correct']}/{summary['rows']}） |",
            f"| 等级（申报选项）识别准确率 | {_percent(summary['option_accuracy'])}"
            f"（{summary['option_correct']}/{summary['rows']}） |",
            f"| 可快速通过·精确率 | {_percent(summary['fast_track_precision'])}"
            f"（TP {summary['true_positive']}，FP {summary['false_positive']}） |",
            f"| 可快速通过·召回率 | {_percent(summary['fast_track_recall'])}"
            f"（FN {summary['false_negative']}） |",
            "",
            "分流：可快速通过 {fast_track} 行，人工复核 {manual} 行，仅提示 {info} 行。".format(
                **summary["routes"]
            ),
            "",
            "可快速通过的条目仍需审核员批量确认；精确率反映“误放行”的风险，召回率反映节省的审核量。",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--date", default=None, help="报告日期（默认今天）")
    args = parser.parse_args(argv)
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    summary = evaluate(dataset, catalog).summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.report is not None:
        from datetime import date

        text = render_report(
            summary,
            dataset=args.dataset.as_posix(),
            synthetic=bool(dataset.get("synthetic")),
            date=args.date or date.today().isoformat(),
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    return summary


if __name__ == "__main__":
    main()
