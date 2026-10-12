"""生成合成演示数据（CLAUDE.md §11：仓库与测试只允许合成数据；学号以 TEST 开头，姓名为“测试学生”）。

用法（输出到已被 .gitignore 排除的 data/ 目录）：
    uv run python scripts/gen_fake_data.py --out data/demo --classes 2 --students 30 --seed 1

生成两个文件，可直接用管理员账号导入：
- users.xlsx：学号、姓名、班级、角色（每班第 1 名同时是班级审核员）
- college.xlsx：学号、学分绩点、第二课堂、公益劳动、体测成绩、宿舍成绩、思想品德四项（全班评议名单）
"""

import argparse
import random
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

USER_HEADER = ["学号", "姓名", "班级", "角色"]
COLLEGE_HEADER = [
    "学号", "学分绩点", "第二课堂", "公益劳动", "体测成绩", "宿舍成绩",
    "政治素养", "品德修养", "纪律观念", "诚信评价",
]  # fmt: skip
MORAL_RANGES = ((6, 10), (6, 10), (3, 5), (3, 5))  # 政治素养、品德修养、纪律观念、诚信评价


def _decimal(rng: random.Random, low: float, high: float, places: int) -> str:
    scale = 10**places
    value = Decimal(rng.randint(round(low * scale), round(high * scale))).scaleb(-places)
    return format(value, "f")


def users_rows(classes: int, students: int) -> list[list[str]]:
    rows = [USER_HEADER]
    for c in range(1, classes + 1):
        for s in range(1, students + 1):
            role = "学生、班级审核员" if s == 1 else "学生"
            rows.append([f"TEST{c:02d}{s:03d}", f"测试学生{c}-{s:02d}", f"测试{c}班", role])
    return rows


def college_rows(classes: int, students: int, seed: int) -> list[list[str]]:
    rng = random.Random(seed)
    rows = [COLLEGE_HEADER]
    for c in range(1, classes + 1):
        for s in range(1, students + 1):
            raters = max(students - 1, 1)  # 全班其他同学评议
            moral = [
                ", ".join(_decimal(rng, low, high, 1) for _ in range(raters))
                for low, high in MORAL_RANGES
            ]
            rows.append(
                [
                    f"TEST{c:02d}{s:03d}",
                    _decimal(rng, 2.0, 4.8, 4),
                    format(Decimal(rng.randint(0, 24)) / 2, "f"),
                    str(rng.randint(0, 14)),
                    _decimal(rng, 50, 98, 1),
                    _decimal(rng, 55, 98, 1),
                    *moral,
                ]
            )
    return rows


def write_xlsx(path: Path, rows: list[list[str]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for row in rows:
        sheet.append(row)  # 一律按文本写入，避免 Excel 把数字转成二进制浮点
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=Path("data/demo"))
    parser.add_argument("--classes", type=int, default=2)
    parser.add_argument("--students", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    write_xlsx(args.out / "users.xlsx", users_rows(args.classes, args.students))
    write_xlsx(args.out / "college.xlsx", college_rows(args.classes, args.students, args.seed))
    print(f"已生成 {args.out / 'users.xlsx'}、{args.out / 'college.xlsx'}")


if __name__ == "__main__":
    main()
