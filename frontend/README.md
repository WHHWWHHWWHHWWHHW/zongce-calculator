# 前端（M2，进行中）

Vue 3 + Vite + TypeScript（strict）。**不实现任何计分逻辑**，即时预估调用后端 `/api/v1/score/preview`（CLAUDE.md §6）。

当前完成的是不依赖组件库的基础部分：类型化 API 客户端、登录态、路由守卫（未登录 / 首次登录强制改密 / 按角色限制）、统一错误处理、单元测试。正式页面等负责人选定组件库（Element Plus 或 Naive UI，CLAUDE.md §13 第 7 项）后实现；`src/views/` 里目前是占位页。

## 开发

```bash
corepack enable                 # 启用 pnpm（版本取自 package.json 的 packageManager）
pnpm install
pnpm dev                        # http://localhost:5173，/api 代理到本机后端 127.0.0.1:8000
```

先按 `docs/本机运行.md` 启动后端。

## 常用命令

| 命令 | 作用 |
|---|---|
| `pnpm gen:api` | 根据 `docs/api/openapi.json` 重新生成 `src/api/schema.d.ts`（后端接口变化后运行） |
| `pnpm check:api` | 检查生成的类型是否与接口文档一致（CI 中执行） |
| `pnpm typecheck` / `pnpm lint` / `pnpm format:check` | 类型检查 / ESLint / Prettier |
| `pnpm test` | 单元测试（Vitest，覆盖率门槛 80%） |
| `pnpm build` | 生产构建，输出到 `dist/` |
