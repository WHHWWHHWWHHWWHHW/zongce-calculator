# 综测智能核算平台 · Zongce Platform

济南大学综合测评项目的平台开发分支，包含学生申报、人工审核、规则核算、排名公示，以及学院名单辅助比对。

本分支 `codex/platform-readme-rules` 基于本地 `m5/rules-v2-engine`（`83b0d1d`）整理，保留完整开发历史。本 README 专门说明平台；原单文件计算器仍可直接打开 [zongce-calculator.html](./zongce-calculator.html)，其说明保留在 [main 分支](https://github.com/WHHWWHHWWHHWWHHW/zongce-calculator/tree/main)。

## 当前实现与边界

| 模块 | 已有实现 | 边界 / 待办 |
| --- | --- | --- |
| 计分引擎 | 独立 Python 包、Decimal、规则版本、计分明细、黄金用例与 legacy 对拍 | 正式规则仍为 ujn-v1；v2 仅有引擎能力，尚未定稿 |
| 学生端 | 登录与首次改密、能力分申报、证明材料、成绩与预估、公示与异议 | 账号由管理员导入，不是学校统一认证 |
| 审核与管理 | 本班申报审核、学院成绩导入、核算、排名、Excel 导出、审计 | 同分排名为 1、2、2、4；任何审核人均不能自审 |
| 辅助比对 | Excel / CSV 名单、带文字层的 PDF / TXT 活动名单，匹配申报并建议快速通过 | 仍需人工确认；图片 / 扫描件 OCR 和大模型尚未接入 |
| 回溯测试 | 对照官方成绩、比较舍入口径、统计报告与本机明细 | 历史报告不等于正式试运行验收通过 |
| 运行方式 | 合成演示库、后端提供前端页面、SQLite 开发、MySQL 迁移 CI | 暂以本机运行为主；Docker Compose、HTTPS、备份恢复部署尚未完成 |

AI 默认配置为 `ZONGCE_AI_PROVIDER=none`，当前主要依靠表格解析与规则匹配。`local` / `remote` 是预留接口，设置环境变量不会自动获得模型能力。准确率和节时指标须经人工标注与独立评测，不能用合成测试结果替代。

## 本机快速体验

准备 **Python 3.11+（可由 uv 管理）**、**uv**、**Node.js 22（与 CI 一致）**、**pnpm 9.15.9（项目锁定版本）**。

```bash
git clone --branch codex/platform-readme-rules https://github.com/WHHWWHHWWHHWWHHW/zongce-calculator.git
cd zongce-calculator
bash scripts/local-demo.sh
```

访问 <http://127.0.0.1:8000>；API 文档位于 <http://127.0.0.1:8000/api/v1/docs>。

| 角色 | 演示账号 |
| --- | --- |
| 学院管理员 | `demo_admin` |
| 班级审核员（兼学生） | `TEST01001`、`TEST02001` |
| 学生 | `TEST01002` 起、`TEST02002` 起 |

随机共用密码在本机 `data/local-demo/演示密码.txt`。演示脚本只使用合成数据，数据库、上传目录和 JWT 密钥放在被 Git 忽略的 `data/local-demo/`；默认仅监听本机。按 `Ctrl+C` 停止。

首次运行会安装依赖；没有 `frontend/dist/index.html` 时会构建前端。更新前端代码后，需要在 `frontend/` 重新执行 `pnpm build`，已有产物时脚本不会自动重建。更新后端代码后需要重启服务。`--reset` 会删除并重建演示目录，仅在确定不需要保留演示数据时使用。

## 开发运行

在仓库根目录安装依赖：

```bash
uv sync --frozen
(cd frontend && pnpm install --frozen-lockfile)
(cd tests/parity && pnpm install --frozen-lockfile)
```

自建开发库时，按 [本机运行文档](./docs/本机运行.md) 配置环境、初始化数据库、创建管理员、导入规则。模板见 [deploy/.env.example](./deploy/.env.example)，配置项使用 `ZONGCE_` 前缀；已有 `.env` 时先检查，避免覆盖配置。

配置完成后在两个终端分别运行：

```bash
# 仓库根目录：后端默认 127.0.0.1:8000
uv run --frozen zongce serve
```

```bash
# frontend/：Vite 默认 localhost:5173，/api 代理到后端
pnpm dev
```

## 目录与数据流

```text
学生申报 / 学院成绩 → 后端权限与审核 → 已通过能力分 + 学院基础数据
                                         ↓
                                  zongce_engine 核算
                                         ↓
                              计分明细 → 排名 → 公示 / 异议
学院获奖名单 → zongce_ai 解析与匹配 → 建议 → 人工确认 → 正常审核流程
```

| 目录 / 文件 | 用途 |
| --- | --- |
| `engine/` | 无 IO 的纯计分包 zongce_engine |
| `rules/` | 计分 JSON Schema、v1 规则、能力分申报目录 |
| `backend/` | FastAPI、SQLAlchemy、Alembic、命令行 zongce |
| `frontend/` | Vue 3、TypeScript、Element Plus、Pinia、Playwright |
| `ai/pipeline/` / `ai/eval/` | 解析匹配、脱敏、评测与人工抽样工具 |
| `tests/golden/` / `tests/parity/` | 黄金用例、Node.js + jsdom 对拍 |
| `scripts/` | 一键检查、演示启动、合成数据生成 |
| `docs/` | 决策记录、接口契约、进度、历史验证报告 |
| `AGENTS.md` | 面向 Codex 等编码助手的开发规则与查找入口 |
| `CLAUDE.md` | 既有项目总指导与历史约定，未经单独授权不修改 |

平台只在引擎中计分，前端通过 `/api/v1/score/preview` 请求预估；分数在 API 中以十进制字符串传输。旧版 HTML 是独立离线工具，不能把它“数据不上传”的说明套用于有服务端、数据库和上传功能的平台。

## 计分口径与未决事项

v1 总分：`round4(综合素质 / 20 × 0.25 + GPA × 0.75)`，GPA 为 5 分制。具体公式见 [rules/ujn-v1.json](./rules/ujn-v1.json)。

- v1 保持 legacy 口径，但按 [ADR 0002](./docs/adr/0002-精确十进制舍入.md) 放行已确认的精确十进制与二进制浮点边界差异。
- v2 已支持阶梯计分、分数线与思想品德附减分，但**没有正式 ujn-v2.json**。第二课堂分数线、附减分上限读法、“放弃”综合素质的处理仍待确认。
- 不根据历史学院表格自行改成截断；现有决定仍采用四舍五入。回溯工具的 truncate 选项用于比较口径。
- 政策原文未入库；项目记录的依据是济大信息院字〔2020〕23 号。未决条款见 [规则疑点清单](./docs/rules-issues.md)，正式使用前需核实适用学年。

## 检查与测试

```bash
# 仓库根目录；需先安装 tests/parity 的依赖并确保 node 在 PATH 中
bash scripts/check.sh

# 前端目录
cd frontend
pnpm check:api
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm exec playwright install chromium  # 首次端到端测试前
pnpm test:e2e
```

Python 检查包括 Ruff、严格 mypy、引擎 / AI 流水线 100% 分支覆盖率、后端至少 80% 覆盖率及 legacy 对拍。前端单元测试覆盖率门槛为 80%；CI 另在 MySQL 8 上验证迁移。这些是检查入口和门槛，实际运行结果见对应日期报告。

macOS 上如果端到端测试等待前端服务超时，检查 Vite 是否只监听 IPv6 `::1`，而测试访问 IPv4 `127.0.0.1`；可用 `NODE_OPTIONS=--dns-result-order=ipv4first pnpm test:e2e`。本分支整理时的环境与结果见 [2026-10-30 验证报告](./docs/reports/platform-verify-20261030.md)。

后端接口变化后同步导出与生成类型：

```bash
uv run --frozen zongce export-openapi docs/api/openapi.json
(cd frontend && pnpm gen:api && pnpm check:api)
```

## 开发文档与数据约定

- 开始开发先读 [AGENTS.md](./AGENTS.md)，再按任务查阅 [CLAUDE.md](./CLAUDE.md)、[进度](./docs/PROGRESS.md) 和 [ADR](./docs/adr/)。
- [回溯测试说明](./docs/回溯测试说明.md)、[AI 评测说明](./ai/eval/README.md)、[前端说明](./frontend/README.md)、[变更记录](./docs/CHANGELOG.md)。
- 真实学生数据、脱敏对照表、脱敏结果、密码、密钥、环境文件、数据库和上传材料只保存在本机，不能提交。测试和演示只使用合成数据；报告仅发布统计结果。

许可证：[Apache License 2.0](./LICENSE)。
