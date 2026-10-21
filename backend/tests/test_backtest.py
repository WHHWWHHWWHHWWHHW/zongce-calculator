"""回溯测试：逐项比对、差异分类、报告不含个人信息（只用合成数据）。"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend_helpers import REPO_ROOT, xlsx
from zongce_backend import cli
from zongce_backend.backtest import BacktestResult, details_csv, parse_table, render_report, run
from zongce_backend.errors import AppError
from zongce_engine import RuleSet

RULES = RuleSet.from_dict(
    json.loads((REPO_ROOT / "rules" / "ujn-v1.json").read_text(encoding="utf-8"))
)
HEADER = [
    "学号", "学分绩点", "第二课堂", "公益劳动", "体测成绩", "宿舍成绩", "能力分",
    "政治素养", "品德修养", "纪律观念", "诚信评价",
    "官方思想品德", "官方综合能力", "官方综合素质（÷20 前）", "官方综测成绩", "备注",
]  # fmt: skip
G1 = ["3.6524", "2.5", "4", "85", "92", "38", "9,8.5,10,7,9.5,8,9,10,6.5,8", "9.5", "4.5", "5"]
G2 = ["5", "4", "4", "90", "90", "38", "9，1，2", "8 6 7", "4.5", "5"]
G3 = ["4.0", "20", "12", "59", "60", "60", "1,2,3,4,10", "12", "5", "5"]
EMPTY_INPUTS = [""] * 10


def _table() -> list[list[str]]:
    return [
        HEADER,
        ["TEST9001", *G1, "27.6250", "51.2500", "78.8750", "3.7252", ""],
        ["TEST9002", *G2, "20.5", "52", "72.5", "4.6563", ""],
        # 中间值舍入口径：5/3 → 1.6667，1.00125 → 1.0013；v1 为 3.0333，R-005 口径为 3.0334
        ["TEST9003", "4.0", "2.0025", *[""] * 4, "1,2,2", "", "", "", "", "", "", "3.0334", ""],
        # 舍入边界：4.6278 × 0.75 = 3.47085，v1 进位为 3.4709，官方（双精度）为 3.4708
        ["TEST9004", "4.6278", *[""] * 12, "3.4708", ""],
        ["TEST9005", *G3, "23", "65", "88", "4.2000", "官方值故意写错"],  # 无法解释
        ["TEST9006", *G1, "", "", "", "3.73", "官方只保留 2 位"],
        ["TEST9007", *G1, "", "", "", "3.72515000001", "Excel 未舍入的存储值"],
        ["", *G1, "", "", "", "3.7252", ""],  # 学号为空
        ["TEST9001", *G1, "", "", "", "3.7252", ""],  # 学号重复
        ["TEST9008", *G1, "", "", "", "缺考", ""],  # 没有可识别的官方结果
        [""] * len(HEADER),  # 空行
    ]


def _result() -> BacktestResult:
    rows, skeleton = parse_table("history.xlsx", xlsx(_table()))
    return run(rows, RULES, skeleton)


def test_compare_and_classify() -> None:
    result = _result()
    assert (result.rows, result.students) == (10, 7)  # 空行不计
    assert dict(result.skipped) == {"学号为空": 1, "学号重复": 1, "没有可识别的官方结果": 1}
    assert result.rounded_officials == 1
    final = result.stats["final_score"]
    assert final.compared == 7
    assert final.matched == {"v1": 4, "intermediate": 5}  # 9001、9002、9006、9007（+ 9003）
    assert dict(final.categories) == {"intermediate": 1, "boundary": 1, "unexplained": 1}
    assert final.max_abs_diff == Decimal("0.1")  # 4.2000 与 4.1000
    for name in ("moral_total", "competence_total", "quality_total"):
        stat = result.stats[name]
        assert (stat.compared, stat.matched["v1"]) == (3, 3)
    assert result.unexplained == 1
    by_student = {d.student: d for d in result.differences}
    assert set(by_student) == {"TEST9003", "TEST9004", "TEST9005"}
    assert by_student["TEST9003"].computed == {"v1": "3.0333", "intermediate": "3.0334"}
    assert by_student["TEST9004"].exact == "3.47085"
    assert result.mapped_columns["能力分"] == "ability"
    assert result.mapped_columns["官方综合素质（÷20 前）"] == "官方 quality_total"
    assert result.ignored_columns == ["备注"]


def test_report_has_statistics_only_and_details_stay_local() -> None:
    result = _result()
    report = render_report(result, label="合成数据", rules=RULES, date="2026-10-20")
    assert "TEST" not in report  # 不含学号
    assert "3.4708" not in report  # 不含个人分数
    assert "| 综测成绩 | 7 | 4（57.14%） | 5（71.43%） | 0.1000 |" in report
    assert "其中 1 处无法用已知口径解释" in report
    assert "跳过：学号为空 1 行；学号重复 1 行；没有可识别的官方结果 1 行" in report
    assert "超过 4 位小数" in report
    assert "未使用的列：备注" in report

    details = details_csv(result)
    assert details.startswith("\ufeff行号,学号")
    assert "TEST9005" in details
    assert "无法解释，需人工核查" in details


def test_report_when_everything_matches() -> None:
    table = "学号,学分绩点,官方综测成绩\nTEST1,4,3\n,,\n"  # 末尾空行忽略
    rows, skeleton = parse_table("ok.csv", table.encode())
    assert skeleton.rows == 1
    result = run(rows, RULES, skeleton)
    report = render_report(result, label="合成数据", rules=RULES, date="2026-10-20")
    assert result.differences == []
    assert "全部比对项上一致" in report
    assert "思想品德" not in report.split("## 结论")[0]  # 没有比对的项目不列出


def test_explained_differences_only() -> None:
    rows, skeleton = parse_table(
        "b.csv", "学号,学分绩点,官方综测成绩\nTEST1,4.6278,3.4708\n".encode()
    )
    report = render_report(run(rows, RULES, skeleton), label="x", rules=RULES, date="d")
    assert "全部差异都可以用上表的已知口径解释" in report


def test_direct_quality_mode_and_missing_subtotals() -> None:
    table = "学号,学分绩点,综合素质评价总分,官方思想品德,官方综测成绩\nTEST1,4,80,24,4\n"
    rows, skeleton = parse_table("d.csv", table.encode())
    assert rows[0].score_input.quality_mode == "direct"
    result = run(rows, RULES, skeleton)
    # 直接输入综合素质时没有思想品德小计，官方给了也无法比对，归为无法解释
    assert [(d.field, d.category, d.computed["v1"]) for d in result.differences] == [
        ("moral_total", "unexplained", "")
    ]


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ("", "表格为空"),
        ("姓名,官方综测成绩\n", "学号"),
        ("学号,学分绩点\n", "官方结果列"),
        ("学号,备注,官方综测成绩\n", "计分输入列"),
    ],
)
def test_bad_headers(table: str, message: str) -> None:
    with pytest.raises(AppError, match=message):
        parse_table("bad.csv", table.encode())


def test_cli_backtest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    table = tmp_path / "history.xlsx"
    table.write_bytes(xlsx(_table()))
    report, details = tmp_path / "report.md", tmp_path / "details.csv"
    cli.main(["backtest", str(table), "--report", str(report), "--details", str(details)])
    out = capsys.readouterr().out
    assert "比对 7 名学生；规则 v1 差异 3 处，其中无法解释 1 处" in out
    assert "TEST" not in report.read_text(encoding="utf-8")
    assert "TEST9005" in details.read_text(encoding="utf-8-sig")

    with pytest.raises(SystemExit, match="data/ 目录"):
        cli.main(["backtest", str(table), "--details", str(REPO_ROOT / "docs" / "x.csv")])
    bad = tmp_path / "bad.csv"
    bad.write_text("学号\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="官方结果列"):
        cli.main(["backtest", str(bad), "--report", str(report), "--details", str(details)])


def test_cli_backtest_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)  # 默认路径落在临时“仓库”里
    table = tmp_path / "t.csv"
    table.write_text("学号,学分绩点,官方综测成绩\nTEST1,4,3\n", encoding="utf-8")
    cli.main(["backtest", str(table)])
    assert len(list((tmp_path / "docs" / "reports").glob("backtest-*.md"))) == 1
    assert len(list((tmp_path / "data" / "backtest").glob("details-*.csv"))) == 1


def test_official_column_override_and_direct_quality(tmp_path: Path) -> None:
    """学院导出模板：综合素质为直接给出的总分，综测成绩列叫“班级测评总分”。"""
    table = [
        ["学年_(必填)", "学号_(必填)", "姓名_(必填)", "综合素质评价成绩_(必填)",
         "学业水平评价成绩_(必填)", "班级测评总分_(必填)"],
        ["12", "TEST1", "虚构", "78.875", "3.6524", "3.7252"],
        ["12", "TEST2", "虚构", "72.5", "5", "4.65625"],  # 未舍入的官方值
    ]  # fmt: skip
    rows, skeleton = parse_table("t.xlsx", xlsx(table), {"班级测评总分": "final_score"})
    assert rows[0].score_input.quality_mode == "direct"
    result = run(rows, RULES, skeleton)
    assert result.stats["final_score"].matched["v1"] == 2
    assert result.rounded_officials == 1
    path = tmp_path / "t.xlsx"
    path.write_bytes(xlsx(table))
    report, details = tmp_path / "r.md", tmp_path / "d.csv"
    cli.main(["backtest", str(path), "--official", "班级测评总分=final_score",
              "--report", str(report), "--details", str(details)])  # fmt: skip
    assert "| 综测成绩 | 2 |" in report.read_text(encoding="utf-8")
    with pytest.raises(SystemExit, match="列名=字段"):
        cli.main(["backtest", str(path), "--official", "班级测评总分=总分"])
