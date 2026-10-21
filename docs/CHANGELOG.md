# 变更记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。legacy 单文件计算器的版本记录见 GitHub Releases（v1.0.0、v1.0.1）。

## [未发布]

### 新增

- 后端 `zongce_backend`（M1）：账号导入与强制改密、JWT + 三种角色、能力分申报与审核、证明材料上传、学院成绩表导入、核算与即时预估、班级排名与 Excel 导出、公示与异议、审计日志；Alembic 迁移；命令行 `zongce`。
- 能力分申报目录 `rules/ability-catalog-xxgc-2020.json`（细则附件 2）。
- `docs/本机运行.md`、`deploy/.env.example`、`docs/api/openapi.json`、`scripts/check.sh`；CI 增加 MySQL 8 迁移任务。
- 计分引擎 `zongce_engine`（`engine/`）：纯 Python、Decimal、无 IO，返回分项明细。
- 规则文件 `rules/ujn-v1.json` 及其 JSON Schema `rules/schema.json`。
- legacy 对拍：jsdom 加载 `zongce-calculator.html`，黄金用例 G1–G3 + 随机 2000 组。
- GitHub Actions：ruff、mypy --strict、pytest（分支覆盖率 100%）、对拍。
- 文档：`CLAUDE.md`、`docs/rules-issues.md`、ADR 0001/0002、`docs/PROGRESS.md`。

### 与 legacy 的已知差异

- 精确值恰在 .5 舍入边界时，引擎按四舍五入进位，legacy 因二进制浮点少 0.0001（约 0.2% 的输入，ADR 0002）。
