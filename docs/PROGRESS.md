# 进度日志

> 每次会话结束时在顶部追加一条（CLAUDE.md §9.3）。

## 2026-10-13 · M1 后端 MVP（无人值守，负责人授权）

**完成**（分支 `m1/backend`，基于 `m0/rule-engine`）

- `backend/`（`zongce_backend`）：FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2；13 张表，迁移 `0001`；统一错误结构。
- 认证与权限：管理员批量导入账号（随机初始密码），首次登录强制改密；JWT；学生 / 班级审核员 / 学院管理员三种角色。
- 能力分申报：增删改查与提交流程；`rules/ability-catalog-xxgc-2020.json` 按细则附件 2 转录（30 个项目，151 个选项，每项注明出处）；建议分、兼职系数、多人分配、分组封顶。
- 证明材料：按文件头识别 PDF/PNG/JPEG，限制大小与数量，随机名存储。
- 审核：通过 / 改分 / 驳回，理由必填；审计日志覆盖全部分数变更。
- 学院成绩表导入（表头关键词沿用 legacy）、单项修改、核算（调用 zongce_engine）、`/api/v1/score/preview`。
- 班级排名（同分并列）、Excel 导出、班级公示（默认 3 天）、异议提交与处理。
- 命令行 `zongce`：init-db / create-admin / load-rules / serve / export-openapi；`docs/本机运行.md`；`deploy/.env.example`；`docs/api/openapi.json`。
- CI：改为调用 `scripts/check.sh`；新增 MySQL 8 迁移任务。ADR 0003。

**验证**（本地，Python 3.12.14）

- `bash scripts/check.sh`：ruff、`mypy --strict`（68 个文件）通过；引擎 + 对拍 129 passed，分支覆盖率 100%；后端 50 passed，覆盖率 98.46%。
- 端到端：导入 G1 数据并审核通过 38 分能力分申报后核算，综测成绩 3.7252，思想品德 27.6250，综合能力 51.2500，与 G1 一致。
- 本机实测：init-db → create-admin → load-rules → serve → 登录 → 建学年 → 预估（3.7252）→ 打开 /api/v1/docs（HTTP 200）。
- MySQL 8：**未验证**（本机没有 MySQL），由 CI 的 mysql 任务验证。

**下一步**

- 负责人确认 ADR 0003 第 6–8 条；审阅 `docs/claude-md-proposals.md`。
- GitHub 推送权限打通后推送分支，开 PR 草稿，确认 CI（含 MySQL 任务）通过。
- M2 前端：等负责人选定组件库（CLAUDE.md §13 第 7 项）。

**阻塞 / 待决定**

- GitHub 推送：Claude 关联的 GitHub 账号暂无本仓库推送权限。
- CLAUDE.md §13 第 6、7 项；R-001～R-005 纳入哪个规则版本。

## 2026-10-12 · M0 规则引擎

**完成**

- 仓库拉到本地；新建分支 `m0/rule-engine`，提交 `CLAUDE.md`。
- `docs/rules-issues.md`：对照《信息学院综合测评实施办法（试行）》（济大信息院字〔2020〕23 号）整理 R-001～R-009。负责人确认该办法现行有效，规则 v1 逐位复现 legacy。
- `tests/parity/`：jsdom 原样加载 `zongce-calculator.html` 并调用其 `calc()`；`tests/golden/cases.json` G1–G3。
- `rules/schema.json`、`rules/ujn-v1.json`：16 条规则，每条都有 id 和 source。
- `engine/`（`zongce_engine`）：Decimal 计算、无 IO、分项明细；122 项单测，分支覆盖率 100%。
- 随机对拍（默认 2000 组，另跑过 20000 组）：无法解释的差异为 0。已知差异只有一类：legacy 二进制浮点在 .5 边界少进 0.0001。负责人决定引擎按精确十进制四舍五入（ADR 0002）。
- ADR 0001（规则引擎结构）、ADR 0002（精确十进制舍入）；GitHub Actions CI。

**验证**（本地，Python 3.12.14 / Node 22.23.2）

- `uv run pytest --cov`：129 passed，分支覆盖率 100%（423 语句 / 86 分支）。
- `PARITY_COUNT=20000 PARITY_SEED=7`：无法解释的差异 0；已知浮点边界差异 189 组，其中综测成绩 38 组。
- `ruff format --check`、`ruff check`、`mypy --strict`：通过。

**下一步**

- 负责人审核 PR 草稿；确认 CI 在 GitHub 上通过。
- M1 开工前确认 CLAUDE.md §13 待确认事项第 3–7 项。第 1 项（能力分细则）已有原文，见 rules-issues。

**阻塞 / 待决定**

- ~~CLAUDE.md §5.1 和 §8 中“与 legacy 0 差异”的表述与 ADR 0002 不一致~~：负责人同意后已更新 CLAUDE.md（同时更新 §13 第 1、3 项：细则原文已提供；部署先在本机运行、暂不购买云服务器）。
- GitHub 推送：Claude 关联的 GitHub 账号暂无本仓库推送权限，分支暂存于本地。
- R-001～R-005（细则与 legacy 的计分差异）需要负责人决定纳入哪个规则版本。
