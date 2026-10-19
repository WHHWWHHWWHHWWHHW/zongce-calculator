# 前端

Vue 3 + Vite + TypeScript（strict）+ Element Plus。**不实现任何计分逻辑**：即时预估调用后端 `/api/v1/score/preview`，分数只做展示与比较（CLAUDE.md §6）。

## 页面

| 角色       | 页面                                                                                             |
| ---------- | ------------------------------------------------------------------------------------------------ |
| 学生       | 我的申报（新建、修改、证明材料、提交、撤回）、我的成绩（含计分明细）、成绩预估、公示与异议       |
| 班级审核员 | 审核工作台：申报分与建议分不一致、需人工给分、未上传材料的行标红；通过 / 改分 / 驳回（理由必填） |
| 班级审核员 | 名单比对：上传学院获奖名单，系统给出“可快速通过 / 人工复核”的建议，勾选后批量确认通过            |
| 学院管理员 | 管理后台：学年与规则、账号导入、成绩表导入、核算与排名、导出 Excel、公示与异议                   |

## 开发

```bash
corepack enable                 # 启用 pnpm（版本取自 package.json 的 packageManager）
pnpm install
pnpm dev                        # http://localhost:5173，/api 代理到本机后端 127.0.0.1:8000
```

先按 `docs/本机运行.md` 启动后端。

## 常用命令

| 命令                                                 | 作用                                                                              |
| ---------------------------------------------------- | --------------------------------------------------------------------------------- |
| `pnpm gen:api`                                       | 根据 `docs/api/openapi.json` 重新生成 `src/api/schema.d.ts`（后端接口变化后运行） |
| `pnpm check:api`                                     | 检查生成的类型是否与接口文档一致（CI 中执行）                                     |
| `pnpm typecheck` / `pnpm lint` / `pnpm format:check` | 类型检查 / ESLint / Prettier                                                      |
| `pnpm test`                                          | 单元测试（Vitest，覆盖率门槛 80%）                                                |
| `pnpm build`                                         | 生产构建，输出到 `dist/`                                                          |
| `pnpm test:e2e`                                      | 构建后运行 Playwright 端到端测试（自动启动一个临时后端，只用合成数据）            |

端到端测试第一次运行前需要下载浏览器：`pnpm exec playwright install chromium`。网络无法下载时，可以用 `PW_CHROMIUM=/path/to/chrome pnpm test:e2e` 指定本机已安装的 Chromium。

设置 `SCREENSHOTS_DIR` 会额外生成演示截图，例如：`SCREENSHOTS_DIR=../docs/reports/screenshots pnpm test:e2e`。
