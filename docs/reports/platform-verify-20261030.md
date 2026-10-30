# 平台分支整理与本机验证（2026-10-30）

## 范围与环境

- 分支：`codex/platform-readme-rules`，基于本地 `m5/rules-v2-engine` 的 `83b0d1d`，保留完整平台提交历史。
- 本次只修改文档：根目录 README、AGENTS、进度、变更记录和本报告；业务代码、计分配置、CLAUDE.md、legacy HTML、依赖锁文件未改。
- 实际本机环境：macOS arm64、Python 3.13.13、Node.js 24.22.1、pnpm 9.15.9、uv 0.13.4。
- CI 配置仍为 Python 3.11 / 3.12、Node.js 22，另有 MySQL 8 迁移任务；本报告不声称验证了该 CI 矩阵。
- Python 使用已有 `.venv-darwin-arm64`；Node 使用当前执行环境提供的运行时，并加入 PATH。未读取或处理真实学生材料。

## 实际验证

| 命令 / 检查 | 结果 |
| --- | --- |
| `UV_PROJECT_ENVIRONMENT=.venv-darwin-arm64 bash scripts/check.sh` | 全部通过；Ruff 格式检查 141 个文件，strict mypy 检查 112 个源文件 |
| 引擎与通用测试（上项包含） | 166 passed，引擎分支覆盖率 100% |
| AI 流水线测试（上项包含） | 83 passed，分支覆盖率 100% |
| 后端测试（上项包含） | 86 passed，覆盖率 99.11% |
| 随机 legacy 对拍（上项包含） | 2000 组；无法解释的差异 0；已知浮点边界差异 20 组，其中综测成绩 2 组，符合 ADR 0002 判定 |
| `pnpm check:api` | 生成类型与 OpenAPI 一致 |
| `pnpm format:check`、`pnpm lint`、`pnpm typecheck` | 均通过 |
| `pnpm test` | 34 passed；行 / 语句覆盖率 100%，分支 98.36%，函数 85.45% |
| `pnpm build` | 通过；保留现有大包体积提示，没有为此修改业务代码 |
| `NODE_OPTIONS=--dns-result-order=ipv4first pnpm test:e2e` | 6 passed，2 skipped；跳过项为需显式设置 SCREENSHOTS_DIR 的桌面 / 手机截图生成 |
| README 相对链接、Markdown 代码围栏、`git diff --check` | 通过 |

端到端测试覆盖管理员准备、学生改密与申报上传、审核员通过、核算与导出、名单比对后人工确认，以及 375px 页面使用；仅操作临时合成测试库。

## 环境问题与处理

1. 默认工具入口提供 pnpm 11.25.0，与项目 packageManager 不同；改用 9.15.9 执行项目检查。
2. 原有 node_modules 缺少 `@rollup/rollup-darwin-arm64`。执行 `CI=true pnpm install --frozen-lockfile` 重新安装后单元测试与构建通过，锁文件未改变。
3. 首次端到端测试等待前端超时。直接检查发现 Vite 在本机只绑定 `::1:4180`，而 Playwright 探测 `127.0.0.1:4180`。通过 `NODE_OPTIONS=--dns-result-order=ipv4first` 统一为 IPv4 后业务用例全部通过，无需修改产品代码。
4. 通过 `pnpm exec playwright install chromium` 安装测试浏览器。截图生成不是本次任务，未设置 SCREENSHOTS_DIR。

## 发布内容核对与未验证项

- 当前跟踪文件没有 data/、real_data/、uploads/、环境密钥文件、数据库或依赖产物；未推送历史的 51 个 blob 中，私有路径及高置信密钥模式检查未发现问题。该检查不是对任意个人信息的自动识别保证。
- 本次文档将开发规则与业务计分配置区分，并把历史授权 / 待办与当前用户任务区分。
- 本机未单独运行 MySQL 8，也未执行 Python 3.11 / 3.12、Node 22 的矩阵测试。
- v2 正式规则、OCR / 模型接入、生产部署仍待后续任务；没有通过本次整理替它们定值或宣布验收。
