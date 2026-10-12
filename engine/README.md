# zongce-engine

综测计分规则引擎（CLAUDE.md §6、§8 M0）。

- 纯 Python 包，只依赖标准库；所有分值用 `decimal.Decimal` 计算，包内不出现 `float`。
- 不做任何 IO：规则文件由调用方读取后交给 `RuleSet.from_dict()`。
- 规则 v1（`rules/ujn-v1.json`）逐位复现 legacy `zongce-calculator.html` v1.0.1。

```python
import json
from decimal import Decimal
from zongce_engine import PeerRatings, RuleSet, ScoreInput, calculate

rules = RuleSet.from_dict(json.load(open("rules/ujn-v1.json", encoding="utf-8")))
result = calculate(ScoreInput(gpa=Decimal("3.6524"), political=PeerRatings((Decimal("9"), Decimal("8")))), rules)
print(result.final_score)          # Decimal，已按规则舍入到 4 位小数
for item in result.items:          # 分项明细：规则 id、原始值、得分、是否封顶
    print(item.rule_id, item.score, item.capped)
```
