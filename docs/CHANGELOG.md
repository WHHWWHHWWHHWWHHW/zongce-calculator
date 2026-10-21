# 变更记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。legacy 单文件计算器的版本记录见 GitHub Releases（v1.0.0、v1.0.1）。

## [未发布]

### 新增

- 回溯测试用于真实数据（M3）：
  - `--official 列名=字段` 指定官方结果列；
  - 新增“最终结果截断到 4 位”口径；
  - 综合素质写“放弃”的按 0 分核算；
  - 报告 `docs/reports/backtest-20261021.md`。
- 引擎可选规则字段 `final.rounding: "truncate"`（R-011），v1 不变。
- 人工抽样核对脚本 `ai/eval/label_sample.py`（抽样表只在本机）。
- 真实表单处理（ADR 0007）：
  - 本机脱敏工具 `ai/eval/desensitize.py`；
  - 活动获奖名单解析，按分值和等级对应申报目录；
  - 按“班级 + 姓名”找学生；
  - 真实表单统计脚本 `ai/eval/real_forms.py`，报告 `docs/reports/real-forms-20261020.md`。
- 名单比对支持带文字的 PDF 和 TXT 活动获奖名单。
- 前端参考智慧济大登录页的配色与版式改版（只借鉴风格）。
- AI 辅助审核基础（M4）：`ai/pipeline`（`zongce_ai`）名单解析、等级规则匹配、与申报匹配和分流；`AI_PROVIDER` 默认 none；名单比对与快速通过批量确认接口和页面；`ai/eval` 评测脚本与合成评测集。
- 回溯测试工具 `zongce backtest`（M3）；引擎可选规则字段 `final.intermediate_decimal_places`（缺省不舍入，v1 结果不变）。
- `zongce seed-demo`：一条命令生成合成演示库。
- 前端（M2，Element Plus）：学生申报、我的成绩、成绩预估、公示与异议、审核工作台（差异标红）、管理后台；Playwright 端到端测试与 375px 检查；演示截图与测试报告草稿。
- 计分明细提供 4 位小数展示值（score_display / raw_display）。
- 后端 `zongce_backend`（M1）：账号导入与强制改密、JWT + 三种角色、能力分申报与审核、证明材料上传、学院成绩表导入、核算与即时预估、班级排名与 Excel 导出、公示与异议、审计日志；Alembic 迁移；命令行 `zongce`。
- 能力分申报目录 `rules/ability-catalog-xxgc-2020.json`（细则附件 2）。
- `docs/本机运行.md`、`deploy/.env.example`、`docs/api/openapi.json`、`scripts/check.sh`；CI 增加 MySQL 8 迁移任务。
- 计分引擎 `zongce_engine`（`engine/`）：纯 Python、Decimal、无 IO，返回分项明细。
- 规则文件 `rules/ujn-v1.json` 及其 JSON Schema `rules/schema.json`。
- legacy 对拍：jsdom 加载 `zongce-calculator.html`，黄金用例 G1–G3 + 随机 2000 组。
- GitHub Actions：ruff、mypy --strict、pytest（分支覆盖率 100%）、对拍。
- 文档：`CLAUDE.md`、`docs/rules-issues.md`、ADR 0001/0002、`docs/PROGRESS.md`。

### 安全

- 登录失败限流：同一账号或同一 IP 在时间窗内失败次数过多时返回 429。
- 排名导出防 Excel 公式注入；下载证明材料加 `X-Content-Type-Options: nosniff`；接口时间统一带 UTC 时区。

### 与 legacy 的已知差异

- 精确值恰在 .5 舍入边界时，引擎按四舍五入进位，legacy 因二进制浮点少 0.0001（约 0.2% 的输入，ADR 0002）。
