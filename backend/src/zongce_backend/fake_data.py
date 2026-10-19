"""合成数据生成。

CLAUDE.md §11：仓库、测试与演示只允许合成数据；学号以 TEST 开头，姓名为“测试学生”。
命令行入口：`scripts/gen_fake_data.py` 生成可导入的 Excel 文件；`zongce seed-demo` 直接生成演示库。
"""

import io
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


def student_id(class_no: int, seat: int) -> str:
    return f"TEST{class_no:02d}{seat:03d}"


def class_name(class_no: int) -> str:
    return f"测试{class_no}班"


def users_rows(classes: int, students: int) -> list[list[str]]:
    """每班第 1 名同时是班级审核员。"""
    rows = [USER_HEADER]
    for c in range(1, classes + 1):
        for s in range(1, students + 1):
            role = "学生、班级审核员" if s == 1 else "学生"
            rows.append([student_id(c, s), f"测试学生{c}-{s:02d}", class_name(c), role])
    return rows


def college_rows(classes: int, students: int, seed: int) -> list[list[str]]:
    """学院成绩表：GPA、基础分四项、思想品德四项（全班其他同学的评议名单）。同一种子结果相同。"""
    rng = random.Random(seed)
    rows = [COLLEGE_HEADER]
    for c in range(1, classes + 1):
        for s in range(1, students + 1):
            raters = max(students - 1, 1)
            moral = [
                ", ".join(_decimal(rng, low, high, 1) for _ in range(raters))
                for low, high in MORAL_RANGES
            ]
            rows.append(
                [
                    student_id(c, s),
                    _decimal(rng, 2.0, 4.8, 4),
                    format(Decimal(rng.randint(0, 24)) / 2, "f"),
                    str(rng.randint(0, 14)),
                    _decimal(rng, 50, 98, 1),
                    _decimal(rng, 55, 98, 1),
                    *moral,
                ]
            )
    return rows


def xlsx_bytes(rows: list[list[str]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for row in rows:
        sheet.append(row)  # 一律按文本写入，避免 Excel 把数字转成二进制浮点
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def write_xlsx(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(xlsx_bytes(rows))
