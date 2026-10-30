# 进度日志

> 每次会话结束时在顶部追加一条（CLAUDE.md §9.3）。

## 2026-10-30 · 完整平台分支、独立 README 与编码助手规则

**完成**
- 按当前用户要求，以本地最新 `m5/rules-v2-engine`（`83b0d1d`）建立 `codex/platform-readme-rules`，保留平台完整提交历史。
- 重写本分支根目录 README：平台功能、运行方法、目录与数据流、验证入口、当前未完成能力；main 分支的离线计算器说明保留在 main。
- 新增根目录 `AGENTS.md`：代码定位、计分与舍入不变量、权限审计、隐私约定、修改和验证流程，以及 v2 未决事项。明确历史授权不扩大当前任务。
- 更新 CHANGELOG，保存 `docs/reports/platform-verify-20261030.md`；CLAUDE.md、legacy HTML、业务代码、规则与锁文件未改。

**验证（本机实际运行）**
- `bash scripts/check.sh`：引擎与通用测试 166 passed（引擎覆盖率 100%），AI 流水线 83 passed（100%），后端 86 passed（99.11%）；Ruff、strict mypy 通过。
- legacy 随机对拍 2000 组：无法解释的差异 0；已知浮点边界差异 20 组（其中综测成绩 2 组）。
- 前端 API 类型、格式、lint、类型检查、构建通过；单元测试 34 passed。
- 端到端业务用例 6 passed；2 个按需截图用例跳过。Mac 上用 IPv4 优先参数解决 Vite / Playwright 监听地址差异；详见报告。

**下一步 / 未决事项**
- 仍需确认 R-001 附减分上限、R-004 第二课堂分数线、R-010“放弃”的平台处理，之后才能编写正式 `ujn-v2.json`。
- OCR / 大模型接入、生产部署等不在本次任务范围内；本机未验证 MySQL 8 与 CI 版本矩阵。
- 旧记录中“需要负责人本机推送”的待办属于历史状态；本次将完整代码集中到上述任务分支，其他里程碑分支保持原状。

## 2026-10-22（通宵，负责人授权）· 本机验证、规则 v2 引擎能力、到梦空间与志愿章导入

**负责人决定（2026-10-22 00:00 前后）**
- R-011：新规则版本按办法原文**四舍五入**。
- R-004：达到分数线后**全部积分**都计；分数线待定。
- R-001 减分上限的读法暂不定。
- 照搬学校统一身份认证登录页的要求没有执行：复刻真实 SSO 页面有钓鱼风险。现有页面只借鉴配色和版式（CLAUDE.md §13 第 9 项）。如需用学校账号登录，应走 CAS 正式对接。

**完成**
- **`m4/local-demo`**（基于 `m3/backtest-real`）：
  - 后端可选提供前端构建产物（`ZONGCE_FRONTEND_DIST`）。
  - `scripts/local-demo.sh`：本机一键演示，使用合成演示库，只监听 127.0.0.1。
  - 负责人在 Mac 终端启动服务后，用 Claude 桌面应用的内置浏览器从本机登录本机后端，按三种角色验证了 19 项功能，全部通过。报告见 `docs/reports/local-verify-20261022.md`。
  - 验证中发现名单比对页没有页面边距，已修复。
- **`m5/rules-v2-engine`**（基于 `m4/local-demo`）：
  - 引擎新增基础分阶梯计分加分数线（`step_capped`）、思想品德附减分（`moral.deduction`，上限和“扣到 0 为止”都做成参数）、输入 `moral_deduction`。v1 结果不变，覆盖率 100%。
  - 学院成绩导入可以直接导入到梦空间学分汇总（“积分总和”→第二课堂）和志愿章汇总（“总章数”→公益劳动）：每个工作表分别识别；没有学号时按“班级 + 姓名”找学生，同班重名或找不到的行报错，不猜测。
  - 用脱敏数据模拟：在有到梦空间记录的学生中，志愿章按班级 + 姓名唯一找到 93.7%，其余是班级对不上，需要人工处理。报告见 `docs/reports/college-sources-20261022.md`。

**下一步**
- 负责人确认：R-004 的分数线、R-001 上限读法、R-010“放弃”怎么处理。确认后编写 `rules/ujn-v2.json`。
- 附减分的数据来源：建议新建“减分记录”表，每条记录事由、分值和次数，供审计；思想品德减分合计由这些记录算出。这一步等 v2 定稿后做，不改 v1 的成绩表结构。
- 推送 `m4/labeling`、`m3/backtest-real`、`m4/local-demo`、`m5/rules-v2-engine`，并创建 PR 草稿。

**阻塞 / 待决定**
- 同上：v2 的三个待定数值或读法；GitHub 推送需要在负责人电脑上执行。

## 2026-10-21（续）· M3 回溯测试用上真实数据、记录负责人决定

**完成**
- **`m3/backtest-real`**（基于 `m4/labeling`）：
  - 人工抽样核对脚本 `ai/eval/label_sample.py`：在本机生成 298 条待标注样本。
  - 回溯工具适配学院导出模板：
    - `--official 列名=字段` 指定官方结果列；
    - 明细可以写到 `real_data/`；
    - 综合素质写“放弃”的按 0 分核算；
    - 新增“最终结果截断到 4 位”口径。
  - 引擎可选规则字段 `final.rounding: "truncate"`，v1 不变。
  - 负责人提供一个班（36 人）的学院导出表，在本机回溯，报告见 `docs/reports/backtest-20261021.md`：
    - 规则 v1（四舍五入）一致 26 人；截断口径一致 34 人。
    - 结论是学院实际按截断计算（新增 R-011）。“放弃”的 5 人综合素质按 0 分计（新增 R-010）。
    - 有 1 处无法解释，需负责人核查。
  - 记录负责人 2026-10-21 的决定：
    - CLAUDE.md §13 第 1、8 项。
    - `docs/rules-issues.md`：R-001、R-002 纳入 v2；R-004 改为阶梯计分加分数线；R-003 暂不处理；R-005 无法用本次数据判断。

**下一步**
- 负责人确认：
  - R-004 的分数线；
  - R-001 减分上限的读法；
  - R-010“放弃”在平台上怎么处理；
  - R-011 采用截断还是四舍五入；
  - 核查回溯中无法解释的 1 处。
- 确认后编写规则 v2，并按新口径导入到梦空间“积分总和”和志愿章“总章数”。志愿章没有学号，需要按班级 + 姓名找学生。

**阻塞 / 待决定**
- `m4/labeling`、`m3/backtest-real` 尚未推送（AI 账号没有仓库写权限，需要在负责人电脑上推送）。

## 2026-10-21 · 真实表单脱敏与学习、名单比对接入活动名单、前端改版（负责人授权）

**完成**
- **`m4/real-forms`**（基于 `m4/ai-basics`）：
  - 负责人提供的 2025–2026 学年各部门综测汇总（25 个文件）已移到本机 `real_data/2025-2026/原始/`（不入库），并在本机脱敏。
  - 脱敏结果：学生姓名 2149 个、教师 36 个、长数字 2723 个；用对照表复查，残留 0 处。
  - 新增模块：
    - `zongce_ai.names`：识别“班级 + 姓名”。
    - `zongce_ai.desensitize`：脱敏。
    - `zongce_ai.activity_lists`：解析活动获奖名单，按分值和等级对应申报选项。
    - `zongce_ai.activity_records`：按班级 + 姓名找学生。
  - 新增脚本：`ai/eval/desensitize.py`、`ai/eval/real_forms.py`。
  - 统计报告 `docs/reports/real-forms-20261020.md`：6434 人次；按班级 + 姓名找到 81.9%，只按姓名唯一找到 13.9%；能确定申报选项 94.8%。
  - ADR 0007；按负责人授权修改 CLAUDE.md（P-008、P-009、真实数据处理规定、待确认第 8、9 项）。
- **`m4/ui-style`**（基于 `m4/real-forms`）：
  - 名单比对支持带文字的 PDF 和 TXT 活动获奖名单（按班级 + 姓名找学生）。
  - 前端参考智慧济大登录页的配色与版式改版：主色 #1665C7，只借鉴风格，不用校徽和照片。
  - 更新截图。

**验证**（云端环境）
- `bash scripts/check.sh` 全部通过：
  - 引擎 + 对拍：133 passed，覆盖率 100%。
  - AI 流水线：80 passed，覆盖率 100%。
  - 后端：78 passed，覆盖率 98.95%。
- 前端：`pnpm test` 34 passed；`pnpm test:e2e` 8 passed，含截图。
- 脱敏与统计在负责人电脑上运行（见上）；你电脑上的完整检查见本次汇报。
- 摸底时打码脚本漏掉了部分文字，**有一部分真实姓名进入了 AI 的工作上下文**（未进入任何文件和提交）。已改为先脱敏后查看（CLAUDE.md §11）。

**下一步**
- 负责人确认：
  - 到梦空间哪一列是第二课堂积分，志愿章哪一项是公益劳动次数（§13 第 8 项）；
  - 赛事“榜内 / 榜外”与一类、二类、三类赛事的对应关系。
- 从脱敏数据中抽样做人工标注，计算识别与匹配的准确率（申报书指标 ≥ 95%）。

**阻塞 / 待决定**
- GitHub 推送：当前登录的 GitHub 账号 `ysy13918253562-dotcom` 没有仓库 `WHHWWHHWWHHWWHHW/zongce-calculator` 的写权限。需要在你电脑上用有权限的账号推送，或把该账号加为协作者。

## 2026-10-20 · M1 加固、中期演示库、M3 回溯工具、M4 基础（无人值守，负责人授权）

**完成**

- `m2/frontend`：
  - 按负责人同意修改 CLAUDE.md（P-001～P-007）。
  - 登录失败限流：同一账号 15 分钟内失败 5 次，或同一 IP 失败 20 次，返回 429（ADR 0005）。
  - `zongce seed-demo`：一条命令生成中期演示库，包括账号、学院成绩、通过 / 改分 / 驳回 / 待审 / 草稿五种申报、核算结果、公示和异议，只能写入空库。
- `m3/backtest`（基于 m2）：
  - 引擎新增可选规则字段 `final.intermediate_decimal_places`（R-005 的另一种读法），v1 结果不变。
  - `zongce backtest`：用历史数据按两种口径重新核算，与官方结果逐项比对。差异分为三类：R-005、舍入边界（R-008）、无法解释。统计报告可以入库；逐条明细只能写到 `data/`。
  - 用法见 `docs/回溯测试说明.md`。
- `m4/ai-basics`（基于 m3）：
  - `ai/pipeline`（`zongce_ai`）：名单解析；把“省一”“金奖”“第五名”等写法规则匹配到申报目录选项，拿不准就不给选项；与申报逐条匹配，按置信度分流；`AI_PROVIDER=none|local|remote`，默认 none；外发前脱敏工具。
  - 接口：`/ai/status`、名单比对（只读）、快速通过批量确认（逐条走审核流程并留痕）。
  - 前端“名单比对”页面。
  - `ai/eval/evaluate.py` 和合成评测集。
  - 详见 ADR 0006。

**验证**（云端环境，Python 3.13.16 / Node 22.22.0 / Chromium 141）

- `bash scripts/check.sh`：
  - ruff、`mypy --strict` 通过。
  - 引擎 + 对拍 133 passed，覆盖率 100%。
  - AI 流水线 44 passed，覆盖率 100%。
  - 后端 75 passed，覆盖率 98.93%。
- `pnpm test` 34 passed；`pnpm test:e2e` 6 passed，另有 2 个截图用例未设 `SCREENSHOTS_DIR` 而跳过。
- 合成评测集（163 行）：学号、等级准确率和快速通过的精确率、召回率均为 100%。**合成数据的写法与匹配规则同源，这个结果不能作为“≥ 95%”的依据**（`ai/eval/README.md`）。
- 你电脑上：同步提交后重新运行全部检查（见本次汇报）。

**下一步**

- M3：负责人提供 1 个班的脱敏历史数据后，运行 `zongce backtest`，逐条核查“无法解释”的差异。
- M4：需要负责人提供脱敏的真实表单样本（§13 第 2 项）、确定大模型与密钥（§13 第 4 项），之后接入 OCR 和大模型抽取，并用真实样本评测。

**阻塞 / 待决定**

- GitHub 推送权限仍未打通，需要在你电脑上推送：`git push -u origin m0/rule-engine m1/backend m2/frontend m3/backtest m4/ai-basics`。
- CLAUDE.md 修改建议 P-008～P-009 待负责人同意。
- R-001～R-005 纳入哪个规则版本。

## 2026-10-19 · M2 前端页面（Element Plus）

**完成**（分支 `m2/frontend`）

- 负责人确认：组件库 Element Plus；ADR 0003 第 6–8 条照此执行。
- 页面：学生申报（含证明材料）、我的成绩、成绩预估、公示与异议；审核工作台（标红：申报分≠建议分、需人工给分、未上传材料）；管理后台（学年与规则、账号导入、成绩表导入、核算与排名、导出、公示与异议）。
- 后端配合：申报目录接口带类型；`create-admin --password-stdin`；异议带学生信息；计分明细提供 4 位小数展示值；命令行释放数据库连接。
- Playwright：主流程（学生申报 → 审核员通过 → 管理员核算导出 → 学生看到 3.3127）+ 375px 检查；演示截图 9 张；测试报告草稿 `docs/reports/test-report-20261019.md`。
- CI 增加端到端任务。

**验证**

- 云端环境（Python 3.13.16 / Node 22.22.0 / Chromium 141）：`bash scripts/check.sh` 引擎 129 passed（覆盖率 100%）、后端 52 passed（98.52%），`-W error::ResourceWarning` 下无警告；`pnpm test` 30 passed；`pnpm test:e2e` 7 passed。
- 你电脑上：同步提交后重新运行全部检查（见本次汇报）。

**下一步**

- M2 验收项已全部完成；推送后确认 CI（含 e2e、MySQL）通过，开 PR 草稿。
- M3 回溯测试需要负责人提供 1 个班的**脱敏**历史综测数据和官方公布结果。

**阻塞 / 待决定**

- GitHub 推送权限仍未打通。
- CLAUDE.md 修改建议 P-001～P-007 待负责人同意。
- R-001～R-005 纳入哪个规则版本。

## 2026-10-13 · M2 前端基础（不依赖组件库）

**完成**（分支 `m2/frontend`，基于 `m1/backend`）

- `frontend/`：Vue 3.5 + Vite 7 + TypeScript 5.9（strict）+ vue-router 4.6 + Pinia 3。
- API 类型由 `docs/api/openapi.json` 生成（openapi-typescript），请求用 openapi-fetch；`pnpm check:api` 校验一致。
- 登录态（sessionStorage）、401 自动登出、修改密码后重新登录；路由守卫：未登录 / 强制改密 / 角色。
- 占位页：登录、改密、首页、审核工作台、管理后台、无权限。
- 安全自查后修复（`m1/backend`）：Excel 导出防公式注入、时间带 UTC 时区、下载加 nosniff。
- CI 增加前端任务；ADR 0004；`frontend/README.md`。
- `scripts/gen_fake_data.py`：生成合成演示数据（users.xlsx、college.xlsx，学号以 TEST 开头），集成测试覆盖“导入 → 核算 → 排名”。

**验证**（本地，Node 22.23.2）

- `pnpm check:api`、`format:check`、`lint`、`typecheck`、`build`：通过。
- `pnpm test`：15 passed；语句 100%、分支 98.61%、函数 87.5%。
- `bash scripts/check.sh`：引擎 + 对拍 129 passed（覆盖率 100%）；后端 52 passed（覆盖率 98.50%）。干净克隆复跑通过。
- 本机联调：`vite preview` + `zongce serve`，经前端代理访问 `/api/v1/health` 和登录成功。
- 浏览器端到端（Playwright）：**未做**，等页面实现后补。

**下一步**

- **负责人选定组件库**（Element Plus 或 Naive UI）后实现页面：学生申报、审核工作台（差异项标红）、管理后台；Playwright 端到端测试；375px 适配。

**阻塞 / 待决定**

- 组件库选择（CLAUDE.md §13 第 7 项）。
- GitHub 推送权限。

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
