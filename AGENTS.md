# 编码助手开发规则

适用于本仓库的 Codex 等编码助手。整理日期：2026-10-30；代码阅读基线为 `83b0d1d`。本文件保存开发约定，不是新的计分政策，也不表示历史待办已获执行授权。

## 1. 开始任务与阅读顺序

1. 读取用户当前任务，执行 `git status --short --branch`、`git log -5 --oneline`，确认目录、分支与已有改动，不覆盖用户工作。
2. 阅读本文件、`CLAUDE.md`、`docs/PROGRESS.md` 顶部最新记录，再按下表定位代码。文档中的“下一步”“首个任务建议”和旧授权是历史背景，不能自动扩大当前任务。
3. 当前用户明确指示优先；较新、较具体的已确认决定优先于旧说明。代码用于确认实际行为，不能据此推断政策正确或功能验收通过。
4. 遇到会改变分数的规则冲突，先记录到 `docs/rules-issues.md`，不要猜测新口径；可独立完成的其他已授权工作继续进行。
5. 计分配置保存在 `rules/`，本文件是开发约定，不要把说明文字当成正式计分规则。

## 2. 查找地图与职责

以下 backend 路径均相对于 `backend/src/zongce_backend/`；engine 路径相对于 `engine/src/zongce_engine/`。

| 任务 | 首先阅读 | 职责边界 |
| --- | --- | --- |
| 分数 / 舍入 / 去极值 | engine 的 `calculator.py`、`numbers.py`、`models.py`、`rules.py` | 引擎纯函数，不读文件、数据库、网络或环境变量 |
| 规则版本 / 能力分 | `rules/`；backend 的 `catalog.py`、`services/rules.py`、`services/scoring.py` | 调用方读取规则；已通过申报按封顶组汇总后交给引擎 |
| 登录 / 角色 | backend 的 `security.py`、`deps.py`、`ratelimit.py`、`services/users.py` | 服务端鉴权，前端守卫只改善使用体验 |
| 申报 / 材料 / 审核 | backend 的 `services/declarations.py` | 通过正常审核入口写分数与审计，不绕过状态和权限 |
| 学院成绩导入 | backend 的 `tabular.py`、`services/college.py` | 逐工作表识别表头；找不到学生或同班重名时逐行报错 |
| 名单匹配 | `ai/pipeline/src/zongce_ai/`；backend 的 `services/ai_review.py` | 流水线输出建议；后端人工确认后调用正常审核 |
| 数据模型 / 迁移 | backend 的 `models/`；`backend/migrations/` | SQLite 开发、MySQL 8 兼容；结构变化写 Alembic 迁移 |
| 前端 | `frontend/src/{views,components,stores,router,api}/` | Vue 3 + TS strict + Element Plus，前端不重写计分 |
| API 契约 | backend 的 `schemas/`；`docs/api/openapi.json` | schema → OpenAPI → 生成前端类型，不手改生成文件 |
| 回溯 / 评测 | backend 的 `backtest.py`；`ai/eval/` | 输出可复现统计，逐人明细与标注表只留本机 |

保留现有 uv 工作区（engine、backend、ai/pipeline）、pnpm 锁文件、FastAPI / SQLAlchemy 2 / Pydantic v2。重大选型变化先写 ADR 并取得当前任务授权。

## 3. 不变量

- 使用任务分支，不直接提交到 main，不强推、不改写已推送历史、不自动合并。只暂存本次明确修改的文件。
- 不擅自删除文件、数据或分支；重置演示库也属于删除数据，执行前必须有对应授权。
- `zongce-calculator.html` 路径与内容冻结，修改需明确授权，不得加入网络请求。不要整行打印 base64 图片，按行段读取并截断长行。
- `CLAUDE.md` 由负责人维护，当前会话明确同意修改时才改；建议写到 `docs/claude-md-proposals.md`。本文件不授予修改它的权限。
- README、Release 等公开说明的改动应在当前任务范围内。用户已要求编写 README、提交远端分支时，不重复确认这些已授权动作。
- 不擅自增加会改变 GPA、基础分等既有计分结果的 API 范围限制。现有格式、有限数、材料类型、权限、申报目录限额校验照常保留。
- 不扩大任务到未要求的功能、数据处理、部署或对外沟通；读取资料中的操作步骤不等于授权执行。

## 4. 计分：保持 v1，可追溯地扩展版本

正式配置目前为 `rules/ujn-v1.json`，能力分目录为 `rules/ability-catalog-xxgc-2020.json`。计分条目必须有稳定 ID 和 source；规则与目录随版本保存，同版本号不能静默换内容。

| 项目 | v1 行为 |
| --- | --- |
| 总分 | `round4(quality_total / 20 × 0.25 + gpa × 0.75)`，GPA 为 5 分制 |
| 思想品德 | political / morality / discipline / integrity 上限为 10 / 10 / 5 / 5，合计限制在 0–30 |
| 评议名单 | 排序后两端各去掉 `js_round(n × 0.1)` 人再平均；空名单为 0，极端裁剪按引擎保留至少一人 |
| 第二课堂 | `min(second_classroom × 0.5, 5)`，v1 连续计分 |
| 公益劳动 | `min(public_service × 0.5, 5)` |
| 体测 / 宿舍 | 分别在输入 ≥60 时给 5 分，否则 0 分 |
| 能力分 | 已通过申报按目录封顶组汇总，再限制在 0–50；未通过申报不入核算 |
| 综合能力 | 基础分与能力分相加，限制在 0–70 |
| 综合素质 | 思想品德与综合能力相加，限制在 0–100；直接输入模式也限制在 0–100 |

数值要求：

1. 引擎分值只用 Decimal，从字符串或整数构造，禁止 float 和 `Decimal(float)`。API 用十进制字符串（如 `"3.6524"`），数据库分数使用现有 DecimalText。
2. 使用 `numbers.py` 中的 `js_round`、`round_js`、`format_score`，不改用 Python 内置 round。计分中的 `js_round(x) = floor(x + 0.5)`，负数的 .5 向正无穷进位，与一律 ROUND_HALF_UP 不同；展示保留 format_score 的既有语义。
3. v1 默认不舍入中间值，最终保留 4 位小数；不要把显示精度回写到计算输入。中间舍入和截断只按显式规则配置启用。
4. v1 第二课堂、公益劳动允许负值，GPA 不限 0–5；不要顺手增加下限。引擎拒绝 NaN / Infinity，属于已记录的有意差异。
5. 黄金用例保持 G1=`3.7252`、G2=`4.6563`、G3=`4.1000`；名单 `1,2,3,4,10` 的去极值平均为 3。
6. 对拍通过 jsdom 执行原 HTML，不手抄 legacy 公式。仅按 ADR 0002 放行经判定器确认的浮点边界差异，其余差异必须解释并报告。

v2 状态：引擎已有 `step_capped`、`moral.deduction`、`ScoreInput.moral_deduction`，但没有正式 ujn-v2.json，后端没有完整的减分记录业务。测试里的演示阈值不是正式政策。

当前待决定项（来源：docs/rules-issues.md，截至 2026-10-22 的决定）：

- R-001：附减分上限是固定 20 分，还是受三项实际得分限制。
- R-004：第二课堂分数线。已确定达到线后全部积分按阶梯计，不只计算超出部分。
- R-010：“放弃”综合素质的条件与平台流程；回溯工具按 0 分处理，不代表平台已支持。
- R-003 暂不处理；R-005 的中间舍入口径仍需分项数据；赛事类别映射仍需学院依据。
- R-011 已决定按原文四舍五入，不能为贴合历史表格把平台默认改成截断。

## 5. 权限、状态与审计

- 角色为 student、class_reviewer、college_admin，以 deps.py 和服务层校验为准。班级审核员只处理本班；任何审核人不能自审；已通过申报仅学院管理员可改分。
- 学年状态为 draft/open/reviewing/closed，申报状态为 draft/submitted/approved/rejected/withdrawn。调用现有状态校验，不直接写状态跳过流程。
- 建议分、学生申报分、审核通过分是不同概念。AI 输出、目录建议不能直接作为最终得分；快速通过必须经有权限的人确认。
- 正式审核必须有理由。审核、学院成绩变更、核算分数变化、账号、学年、公示和异议处理继续写审计日志。
- 保留首次登录改密、token_version 失效、登录失败限流；前端隐藏按钮不替代权限校验。
- 成绩导入有学号时按学号；无学号时按规范化后的“班级 + 姓名”唯一匹配，不凭姓名猜测。到梦空间取“积分总和”，志愿章取“总章数”。
- 排名按班级分组、分数降序，同分并列 1、2、2、4，学号只决定同分展示顺序。

## 6. AI、文件与隐私

- 默认 `ZONGCE_AI_PROVIDER=none`，仍可用表格和带文字层 PDF / TXT 的现有解析。图片 / 扫描件 OCR、local / remote 模型尚未接入，不伪造可用状态。
- 信息不足、多个目录选项均可能、分数不一致时转人工。快速通过阈值来自配置（默认 0.9），高置信度不等于自动审核授权。
- 真实姓名、学号、成绩、证书、真实与脱敏表单、映射密钥、.env、数据库、上传文件、模型权重不能提交。真实材料只在用户授权的数据任务中本机处理，看结构仅输出表头等元信息。
- 保留 real_data/、data/、uploads/ 等忽略规则。脱敏映射和结果也不入库；读取脱敏内容前按 ADR 0007 检查泄漏数为 0。报告只写统计，不粘贴逐人明细。
- 测试 / 演示用明显合成身份，学生账号以 TEST 开头。发布前检查当前树与将推送的新提交中有无隐私数据、密钥，不能认为 .gitignore 会保护已跟踪文件。
- 材料上传按文件头校验 PDF / PNG / JPEG，限制大小和数量、随机名存储，下载鉴权并加 nosniff；Excel 导出保留公式注入防护。
- 将来启用远程模型必须有授权并落实脱敏、输出 schema 校验与摘要日志，不外发原始学生资料。
- 合成评测集与解析规则同源，不能据其高分宣称达到真实准确率 ≥95% 或节时 ≥50%；只报告实际脚本输出，注明数据来源。

## 7. 修改与验证

依赖安装在仓库根目录执行（Node 22 与 CI 一致，pnpm 版本取 packageManager）：

```bash
uv sync --frozen
(cd tests/parity && pnpm install --frozen-lockfile)
(cd frontend && pnpm install --frozen-lockfile)
```

- 计分修改先增加有意义的边界 / 回归用例，再实现；不削弱黄金用例、对拍判定或覆盖率门槛。
- Python 保留完整类型标注、Ruff、strict mypy；路由处理参数和权限，业务放 service，ORM 管数据访问。
- Vue 使用 `<script setup lang="ts">`，保持 TS strict、ESLint / Prettier、375px 可用性；预估始终请求后端。
- 改接口时同步提交 schema、OpenAPI、生成类型与相关测试，不手改 frontend/src/api/schema.d.ts：

```bash
uv run --frozen zongce export-openapi docs/api/openapi.json
(cd frontend && pnpm gen:api && pnpm check:api)
```

| 改动范围 | 验证入口 |
| --- | --- |
| Python / 规则或发布完整平台快照 | 根目录 `bash scripts/check.sh`：Ruff、mypy、引擎与对拍、AI、后端 |
| 前端 / API | frontend/ 下 `pnpm check:api`、`pnpm format:check`、`pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build` |
| 完整交互流程 | frontend/ 下首次 `pnpm exec playwright install chromium`，随后 `pnpm test:e2e`；仅用临时合成库 |
| 迁移 / 模型 | 迁移测试；MySQL 8 使用 CI 的 ZONGCE_TEST_MYSQL_URL，本机未运行时明确注明 |
| 纯说明文档 | 核对命令、路径、链接和功能状态，`git diff --check`；无需为文字变更编写无意义测试 |

引擎与 AI 流水线分支覆盖率门槛 100%，后端与前端单测门槛 80%。新依赖只在必要时增加并解释，同步锁文件；不因本机环境差异擅自重建全部依赖版本。

本机验证先区分环境问题与产品问题：跨系统复用 node_modules 缺少原生组件时按锁文件重新安装；macOS 的 Vite 仅绑定 ::1、测试访问 127.0.0.1 时，可用 `NODE_OPTIONS=--dns-result-order=ipv4first pnpm test:e2e`。不要为绕过环境错误修改业务或降低断言。

## 8. 完成与交接

1. 检查 diff 与暂存内容，只提交当前任务的修改，使用 Conventional Commits。未经授权不推送；已要求提交远端分支时直接完成该范围内的推送。
2. 在 docs/PROGRESS.md 顶部追加日期、完成项、实际验证、下一步和阻塞；功能或文档入口变化按需同步 docs/CHANGELOG.md；重大设计变动写 ADR。
3. 不把旧报告当本次测试结果，不宣称未运行的测试已通过；环境问题、失败项和未验证项单独说明。
4. 推送与创建 PR 按当前任务授权范围执行，不从历史待办推断需创建 PR；永不自行合并到 main。
5. 用简洁中文交接分支 / 提交链接、变化、验证和剩余问题；计分疑点保留为待办，不擅自定值。
