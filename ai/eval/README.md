# AI 辅助审核评测

报告中的准确率、精确率、召回率必须来自 `evaluate.py` 的输出（CLAUDE.md §3 第 8 条、§8 M4）。评测集只能是合成数据或已脱敏数据。

```bash
uv run python scripts/gen_fake_data.py --ai-eval ai/eval/datasets/award-lists-synthetic.json   # 生成合成评测集
uv run python ai/eval/evaluate.py ai/eval/datasets/award-lists-synthetic.json                   # 输出指标（JSON）
uv run python ai/eval/evaluate.py <评测集> --report docs/reports/ai-eval-YYYYMMDD.md              # 另写一份报告
```

## 指标

| 指标 | 含义 |
|---|---|
| 学号识别准确率 | 名单每一行解析出的学号与标注一致的比例 |
| 等级识别准确率 | 解析出的申报选项与标注一致的比例（标注为“无法确定”时，不猜即为正确） |
| 可快速通过·精确率 | 建议快速通过的条目中，确实应当快速通过的比例；越低越容易误放行 |
| 可快速通过·召回率 | 应当快速通过的条目中，被建议快速通过的比例；反映节省的审核量 |

## 评测集格式

`datasets/*.json`：`cases` 中每一项是一份名单，包括 `catalog_item`（申报项目）、`context`（整表说明，如“一类赛事”）、`rows`（含表头的二维表）、`students`、`declarations`（已提交的申报），以及逐行标注 `truth`（`row`、`student_id`、`option_code`、`fast_track`）。

## 注意

合成评测集由 `zongce_backend.fake_data.award_eval_dataset` 生成，用到的写法（“省一”“金奖”、全角学号等）与匹配规则同源，**在它上面的结果只能说明流水线在已知写法上工作正常，不能作为申报书中“识别与匹配准确率 ≥ 95%”的依据**。这一指标要用负责人提供的脱敏真实名单来测（CLAUDE.md §13 第 2 项）。
