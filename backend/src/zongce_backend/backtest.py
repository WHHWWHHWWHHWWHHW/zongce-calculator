"""回溯测试（CLAUDE.md §8 M3）：用历史输入重新核算，与官方公布结果逐项比对。

- 输入：一个班的历史数据表（.xlsx / .csv）。每行一名学生，包括计分输入（学分绩点、第二课堂、
  公益劳动、体测、宿舍、能力分、思想品德四项的分数或评议名单）和官方结果（列名以“官方”“公布”
  或“公示”开头，如“官方综测成绩”“官方综合素质”“官方思想品德”“官方综合能力”）。
- 口径：规则 v1（精确十进制，只舍入最终结果）、“中间值也舍入到 4 位”（R-005）、
  “最终结果截断到 4 位”（R-011）。
- 差异分类：可由 R-005 解释；可由截断解释（R-011）；舍入边界（R-008：精确值恰在 .5 边界，
  官方少进位一位）；无法解释。
- 综合素质列写“放弃”的学生按 0 分核算（学院导出表的做法，R-010），报告中单独计数。
- 输出：统计报告（不含学号、姓名、分数明细，可以入库）和逐条明细（只能留在本机 data/ 或
  real_data/ 目录）。

只做比对，不写数据库。
"""

import csv
import io
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from decimal import ROUND_FLOOR, Decimal

from zongce_engine import (
    MoralValue,
    PeerRatings,
    RuleSet,
    ScoreInput,
    ScoreResult,
    calculate,
    extract_numbers,
    format_score,
)

from .errors import AppError
from .models import MORAL_SCORE_FIELDS, ScoreField
from .services.college import STUDENT_COLUMN, match_field, normalize_label
from .tabular import read_table

OFFICIAL_PREFIXES = ("官方", "公布", "公示")
ABILITY_KEYWORDS = ("能力分",)
MAX_PLACES = 4

# 可比对的结果项：字段名 → (中文名, 官方列的关键词)
RESULT_FIELDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "final_score": ("综测成绩", ("综测成绩", "综合测评成绩", "综合测评", "综测", "总分")),
    "quality_total": ("综合素质评价", ("综合素质评价成绩", "综合素质评价", "综合素质")),
    "moral_total": ("思想品德行为习惯", ("思想品德行为习惯", "思想品德")),
    "competence_total": ("综合能力表现", ("综合能力表现", "综合能力")),
}

HYPOTHESES: dict[str, str] = {
    "v1": "规则 v1（精确十进制，只舍入最终结果）",
    "intermediate": "中间值也舍入到 4 位（R-005）",
    "truncate": "最终结果截断到 4 位（R-011）",
}
CATEGORIES: dict[str, str] = {
    "intermediate": "可由 R-005（中间值舍入）解释",
    "truncate": "可由截断解释（R-011）",
    "boundary": "舍入边界（R-008：精确值恰在 .5 边界，官方少进位）",
    "unexplained": "无法解释，需人工核查",
}
# 综合素质列中表示“放弃综合素质评价”的写法；学院导出表按 0 分计入总分（R-010）
WAIVED_WORDS = ("放弃",)


@dataclass(frozen=True)
class Official:
    text: str
    value: Decimal
    places: int
    rounded: bool  # 官方值超过 4 位小数（如 Excel 未舍入的存储值），按 4 位比较


@dataclass(frozen=True)
class BacktestRow:
    row: int
    student: str
    score_input: ScoreInput
    official: Mapping[str, Official]
    waived: bool = False  # 综合素质写“放弃”，按 0 分核算


@dataclass(frozen=True)
class Difference:
    row: int
    student: str
    field: str
    official: str
    computed: dict[str, str]  # 各口径在比较精度下的值
    exact: str  # 规则 v1 的精确值（未舍入）
    category: str


@dataclass
class FieldStat:
    compared: int = 0
    matched: dict[str, int] = field(default_factory=lambda: dict.fromkeys(HYPOTHESES, 0))
    max_abs_diff: Decimal = Decimal(0)  # 规则 v1 在比较精度下的最大偏差
    categories: Counter[str] = field(default_factory=Counter)


@dataclass
class BacktestResult:
    rows: int
    students: int
    skipped: Counter[str]
    mapped_columns: dict[str, str]
    ignored_columns: list[str]
    stats: dict[str, FieldStat]
    differences: list[Difference]
    rounded_officials: int
    waived: int = 0

    @property
    def unexplained(self) -> int:
        return sum(1 for d in self.differences if d.category == "unexplained")


def _places(text: str) -> int:
    _, _, fraction = text.partition(".")
    return len(fraction)


def _official_field(label: str) -> str | None:
    norm = normalize_label(label)
    if not norm.startswith(OFFICIAL_PREFIXES):
        return None
    best: str | None = None
    best_len = 0
    for name, (_, keywords) in RESULT_FIELDS.items():
        for keyword in keywords:
            if keyword in norm and len(keyword) > best_len:
                best, best_len = name, len(keyword)
    return best


@dataclass(frozen=True)
class _Columns:
    student: int
    inputs: dict[int, ScoreField]
    ability: int | None
    official: dict[int, str]
    ignored: list[str]


def _columns(header: list[str], official_columns: Mapping[str, str] | None = None) -> _Columns:
    student = next((i for i, h in enumerate(header) if STUDENT_COLUMN in h), None)
    if student is None:
        raise AppError("表头缺少“学号”列")
    inputs: dict[int, ScoreField] = {}
    official: dict[int, str] = {}
    ability: int | None = None
    ignored: list[str] = []
    for col, label in enumerate(header):
        if col == student or not label:
            continue
        overrides = official_columns or {}
        result_field = next(
            (f for key, f in overrides.items() if key in normalize_label(label)), None
        ) or _official_field(label)
        if result_field is not None and result_field not in official.values():
            official[col] = result_field
            continue
        if result_field is None and ability is None and any(k in label for k in ABILITY_KEYWORDS):
            ability = col
            continue
        input_field = None if result_field is not None else match_field(label)
        if input_field is not None and input_field not in inputs.values():
            inputs[col] = input_field
        else:
            ignored.append(label)
    if not official:
        raise AppError("没有识别出官方结果列：列名应以“官方”“公布”或“公示”开头，如“官方综测成绩”")
    if not inputs and ability is None:
        raise AppError("没有识别出任何计分输入列，请检查表头")
    return _Columns(student, inputs, ability, official, ignored)


def _number(text: str) -> Decimal | None:
    numbers = extract_numbers(text)
    return numbers[0] if numbers else None


def _moral(text: str) -> MoralValue:
    numbers = extract_numbers(text)
    if len(numbers) >= 2:
        return PeerRatings(tuple(numbers))
    return numbers[0] if numbers else None


def _row_input(row: list[str], cols: _Columns) -> tuple[ScoreInput, bool]:
    """一行的计分输入；第二个值表示综合素质写的是“放弃”（按 0 分核算）。"""

    def cell(col: int) -> str:
        return row[col].strip() if col < len(row) else ""

    values: dict[str, object] = {}
    waived = False
    for col, input_field in cols.inputs.items():
        text = cell(col)
        if not text:
            continue
        if input_field is ScoreField.QUALITY_DIRECT and text in WAIVED_WORDS:
            values[input_field.value], waived = Decimal(0), True
        elif input_field in MORAL_SCORE_FIELDS:
            values[input_field.value] = _moral(text)
        else:
            values[input_field.value] = _number(text)
    if cols.ability is not None and cell(cols.ability):
        values["ability"] = _number(cell(cols.ability))
    if values.get("quality_direct") is not None:
        values["quality_mode"] = "direct"
    return ScoreInput(**values), waived  # type: ignore[arg-type]


def _official(text: str) -> Official | None:
    numbers = extract_numbers(text)
    if len(numbers) != 1:
        return None
    value = numbers[0]
    places = _places(format(value, "f"))
    if places > MAX_PLACES:
        return Official(text, Decimal(format_score(value, MAX_PLACES)), MAX_PLACES, True)
    return Official(text, value, places, False)


def parse_table(
    filename: str, data: bytes, official_columns: Mapping[str, str] | None = None
) -> tuple[list[BacktestRow], BacktestResult]:
    """读取历史数据表。返回可比对的行，以及只填好表头和跳过信息的结果骨架。

    official_columns：列名关键词 → 结果字段，用于官方结果列不以“官方”开头的表
    （如学院导出模板的“班级测评总分”= final_score）。
    """
    rows = read_table(filename, data)
    if not rows:
        raise AppError("表格为空")
    header = rows[0]
    cols = _columns(header, official_columns)
    parsed: list[BacktestRow] = []
    skipped: Counter[str] = Counter()
    seen: set[str] = set()
    for number, row in enumerate(rows[1:], start=2):  # read_table 已去掉空行
        student = row[cols.student].strip() if cols.student < len(row) else ""
        if not student:
            skipped["学号为空"] += 1
            continue
        if student in seen:
            skipped["学号重复"] += 1
            continue
        seen.add(student)
        official: dict[str, Official] = {}
        for col, result_field in cols.official.items():
            text = row[col].strip() if col < len(row) else ""
            value = _official(text) if text else None
            if value is not None:
                official[result_field] = value
        if not official:
            skipped["没有可识别的官方结果"] += 1
            continue
        score_input, waived = _row_input(row, cols)
        parsed.append(BacktestRow(number, student, score_input, official, waived))
    skeleton = BacktestResult(
        rows=len(rows) - 1,
        students=len(parsed),
        skipped=skipped,
        mapped_columns={
            **{header[c]: f.value for c, f in cols.inputs.items()},
            **({header[cols.ability]: "ability"} if cols.ability is not None else {}),
            **{header[c]: f"官方 {f}" for c, f in cols.official.items()},
        },
        ignored_columns=cols.ignored,
        stats={},
        differences=[],
        rounded_officials=sum(o.rounded for r in parsed for o in r.official.values()),
        waived=sum(r.waived for r in parsed),
    )
    return parsed, skeleton


def _value(result: ScoreResult, result_field: str) -> Decimal | None:
    value: Decimal | None = getattr(result, result_field)
    return value


def _exact(result: ScoreResult, result_field: str) -> Decimal | None:
    return result.final_score_raw if result_field == "final_score" else _value(result, result_field)


def _at(value: Decimal | None, places: int) -> Decimal | None:
    return None if value is None else Decimal(format_score(value, places))


def _on_half_boundary(value: Decimal, places: int) -> bool:
    shifted = value.scaleb(places)
    return shifted - shifted.to_integral_value(rounding=ROUND_FLOOR) == Decimal("0.5")


def run(rows: list[BacktestRow], rules: RuleSet, skeleton: BacktestResult) -> BacktestResult:
    """按各口径核算并与官方结果比对。"""
    variants = {
        "v1": rules,
        "intermediate": replace(
            rules, final=replace(rules.final, intermediate_decimal_places=MAX_PLACES)
        ),
        "truncate": replace(rules, final=replace(rules.final, rounding="truncate")),
    }
    stats = {name: FieldStat() for name in RESULT_FIELDS}
    differences: list[Difference] = []
    for row in rows:
        results = {name: calculate(row.score_input, ruleset) for name, ruleset in variants.items()}
        for result_field, official in row.official.items():
            stat = stats[result_field]
            stat.compared += 1
            computed = {
                name: _at(_value(result, result_field), official.places)
                for name, result in results.items()
            }
            for name, value in computed.items():
                if value == official.value:
                    stat.matched[name] += 1
            v1 = computed["v1"]
            if v1 is not None:
                stat.max_abs_diff = max(stat.max_abs_diff, abs(v1 - official.value))
            if v1 == official.value:
                continue
            exact = _exact(results["v1"], result_field)
            if computed["intermediate"] == official.value:
                category = "intermediate"
            elif computed["truncate"] == official.value:
                category = "truncate"
            elif (
                exact is not None
                and v1 is not None
                and _on_half_boundary(exact, official.places)
                and official.value == v1 - Decimal(1).scaleb(-official.places)
            ):
                category = "boundary"
            else:
                category = "unexplained"
            stat.categories[category] += 1
            differences.append(
                Difference(
                    row=row.row,
                    student=row.student,
                    field=result_field,
                    official=official.text,
                    computed={k: "" if v is None else format(v, "f") for k, v in computed.items()},
                    exact="" if exact is None else format(exact.normalize(), "f"),
                    category=category,
                )
            )
    return replace(skeleton, stats=stats, differences=differences)


def details_csv(result: BacktestResult) -> str:
    """逐条差异明细（含学号与分数），只能保存在本机 data/ 或 real_data/，不得提交或写进报告。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["行号", "学号", "项目", "官方值", *(HYPOTHESES[h] for h in HYPOTHESES), "v1 精确值",
         "分类", "人工核查说明"]
    )  # fmt: skip
    for d in result.differences:
        writer.writerow(
            [d.row, d.student, RESULT_FIELDS[d.field][0], d.official,
             *(d.computed[h] for h in HYPOTHESES), d.exact, CATEGORIES[d.category], ""]
        )  # fmt: skip
    return "﻿" + buffer.getvalue()  # 带 BOM，Excel 直接打开不乱码


def _percent(part: int, whole: int) -> str:
    return "—" if whole == 0 else f"{Decimal(part * 100) / Decimal(whole):.2f}%"


def render_report(result: BacktestResult, *, label: str, rules: RuleSet, date: str) -> str:
    """统计报告（Markdown）。只含计数和比例，不含学号、姓名或任何个人分数。"""
    lines = [
        f"# 回溯测试报告（{date}）",
        "",
        f"- 数据：{label}。明细只保存在本机 `data/` 或 `real_data/` 目录，"
        "不入库（CLAUDE.md §11）。",
        f"- 规则：{rules.id} {rules.version}；比较精度：按官方结果的小数位数（最多 4 位）。",
        f"- 样本：表格 {result.rows} 行，参与比对 {result.students} 名学生。",
    ]
    if result.skipped:
        reasons = "；".join(f"{k} {v} 行" for k, v in sorted(result.skipped.items()))
        lines.append(f"- 跳过：{reasons}。")
    if result.waived:
        lines.append(
            f"- 有 {result.waived} 名学生的综合素质写“放弃”，按 0 分核算"
            "（学院导出表的做法，见 docs/rules-issues.md R-010）。"
        )
    if result.rounded_officials:
        lines.append(
            f"- 有 {result.rounded_officials} 个官方值超过 4 位小数"
            "（可能是 Excel 中未舍入的存储值），已先四舍五入到 4 位再比较。"
        )
    lines += [
        "- 生成命令：`uv run zongce backtest <数据表>`"
        "（`backend/src/zongce_backend/backtest.py`）。",
        "",
        "## 逐项一致率",
        "",
        "| 项目 | 比对人数 | " + " | ".join(HYPOTHESES.values()) + " | 规则 v1 最大偏差 |",
        "|---|---:|" + "---:|" * len(HYPOTHESES) + "---:|",
    ]
    for name, (title, _) in RESULT_FIELDS.items():
        stat = result.stats[name]
        if stat.compared == 0:
            continue
        cells = [
            f"{stat.matched[h]}（{_percent(stat.matched[h], stat.compared)}）" for h in HYPOTHESES
        ]
        lines.append(
            f"| {title} | {stat.compared} | " + " | ".join(cells) + f" | {stat.max_abs_diff} |"
        )
    lines += [
        "",
        "## 规则 v1 差异分类",
        "",
        "| 项目 | 差异数 | " + " | ".join(CATEGORIES.values()) + " |",
        "|---|---:|" + "---:|" * len(CATEGORIES) + "",
    ]
    for name, (title, _) in RESULT_FIELDS.items():
        stat = result.stats[name]
        if stat.compared == 0:
            continue
        total = sum(stat.categories.values())
        cells = [str(stat.categories[c]) for c in CATEGORIES]
        lines.append(f"| {title} | {total} | " + " | ".join(cells) + " |")
    lines += ["", "## 结论", ""]
    if not result.differences:
        lines.append("- 规则 v1 与官方结果在全部比对项上一致。")
    else:
        lines.append(f"- 规则 v1 与官方结果共有 {len(result.differences)} 处差异。")
        if result.unexplained:
            lines.append(
                f"- **其中 {result.unexplained} 处无法用已知口径解释**，必须逐条人工核查"
                "（本机明细文件“人工核查说明”一列），查明原因后补充到本报告。"
            )
        else:
            lines.append("- 全部差异都可以用上表的已知口径解释。")
    lines += [
        "",
        "## 识别的列",
        "",
        "| 表头 | 字段 |",
        "|---|---|",
        *(f"| {k} | {v} |" for k, v in result.mapped_columns.items()),
    ]
    if result.ignored_columns:
        lines += ["", f"未使用的列：{'、'.join(result.ignored_columns)}。"]
    return "\n".join(lines) + "\n"
