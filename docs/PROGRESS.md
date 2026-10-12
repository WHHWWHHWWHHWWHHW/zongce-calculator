# 进度日志

> 每次会话结束时在顶部追加一条（CLAUDE.md §9.3）。

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

- CLAUDE.md §5.1 和 §8 M0 中“与 legacy 0 差异”的表述与 ADR 0002 的决定不一致。CLAUDE.md 由负责人维护，是否修改由负责人决定。
- R-001～R-005（细则与 legacy 的计分差异）需要负责人决定纳入哪个规则版本。
