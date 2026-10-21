# 变更记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。legacy 单文件计算器的版本记录见 GitHub Releases（v1.0.0、v1.0.1）。

## [未发布]

### 新增

- 计分引擎 `zongce_engine`（`engine/`）：纯 Python、Decimal、无 IO，返回分项明细。
- 规则文件 `rules/ujn-v1.json` 及其 JSON Schema `rules/schema.json`。
- legacy 对拍：jsdom 加载 `zongce-calculator.html`，黄金用例 G1–G3 + 随机 2000 组。
- GitHub Actions：ruff、mypy --strict、pytest（分支覆盖率 100%）、对拍。
- 文档：`CLAUDE.md`、`docs/rules-issues.md`、ADR 0001/0002、`docs/PROGRESS.md`。

### 与 legacy 的已知差异

- 精确值恰在 .5 舍入边界时，引擎按四舍五入进位，legacy 因二进制浮点少 0.0001（约 0.2% 的输入，ADR 0002）。
