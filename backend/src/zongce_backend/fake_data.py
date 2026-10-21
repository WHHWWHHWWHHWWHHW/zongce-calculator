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


# ---------- AI 辅助审核评测集（ai/eval）：合成的获奖名单 + 申报 + 标注 ----------

_LEVEL_TEXT = {
    "national": ("国家级", "全国", "国家级"),
    "provincial": ("省级", "省部级", "山东省"),
    "university": ("校级", "济南大学", "校级"),
}
_LEVEL_ABBR = {"national": "国", "provincial": "省", "university": "校"}
_RANK_TEXT = {
    "1": ("一等奖", "一等", "金奖"),
    "2": ("二等奖", "二等", "银奖"),
    "3": ("三等奖", "三等", "铜奖"),
}
_RANK_ABBR = {"1": "一", "2": "二", "3": "三"}
_CN = "一二三四五六七八"
_FULL_WIDTH = str.maketrans("0123456789", "０１２３４５６７８９")


def _award_text(rng: random.Random, level: str, rank: str) -> str:
    if rng.random() < 0.2:
        return f"{_LEVEL_ABBR[level]}{_RANK_ABBR[rank]}"  # 省一
    return f"{rng.choice(_LEVEL_TEXT[level])} {rng.choice(_RANK_TEXT[rank])}"


def _games_text(rng: random.Random, option: str) -> str:
    event, place = option.split("_")
    number = int(place)
    event_text = rng.choice(("个人项目", "个人")) if event == "individual" else "接力"
    place_text = _CN[number - 1] if rng.random() < 0.5 else str(number)
    return f"{event_text} 第{place_text}名"


def _list_spec(item: str, class_no: int | None) -> tuple[str, str, list[str]]:
    """返回 (申报项目, 整表说明, 可选的选项编码)。"""
    if item == "competition":
        assert class_no is not None
        codes = [f"c{class_no}_{lv}_{rk}" for lv in _LEVEL_TEXT for rk in _RANK_TEXT]
        return item, f"{_CN[class_no - 1]}类赛事", codes
    if item == "volunteer_contest":
        return item, "", [f"{lv}_{rk}" for lv in _LEVEL_TEXT for rk in _RANK_TEXT]
    return item, "", [f"{ev}_{n}" for ev in ("individual", "relay") for n in range(1, 9)]


def _option_text(rng: random.Random, item: str, code: str) -> str:
    if item == "university_games":
        return _games_text(rng, code)
    level, rank = code.split("_")[-2:]
    return _award_text(rng, level, rank)


def award_eval_dataset(seed: int = 1, rows_per_list: int = 40) -> dict[str, object]:
    """生成评测集：若干份获奖名单，每行带标注（真实学号、真实选项、是否应快速通过）。

    噪声：全角学号、学号不存在、姓名不符、申报等级不同、未申报、重复行、等级写法无法识别。
    """
    rng = random.Random(seed)
    lists = [("competition", 1), ("competition", 2), ("volunteer_contest", None),
             ("university_games", None)]  # fmt: skip
    cases: list[dict[str, object]] = []
    next_declaration = 1
    for index, (item_code, class_no) in enumerate(lists, start=1):
        item, context, codes = _list_spec(item_code, class_no)
        header = ["序号", "学号", "姓名", "获奖等级", "备注"]
        rows: list[list[str]] = [header]
        truth: list[dict[str, object]] = []
        students: list[dict[str, str]] = []
        declarations: list[dict[str, object]] = []
        for seat in range(1, rows_per_list + 1):
            sid = student_id(index, seat)
            name = f"测试学生{index}-{seat:02d}"
            code = rng.choice(codes)
            students.append({"student_id": sid, "name": name})
            text = _option_text(rng, item, code)
            truth_code: str | None = code
            shown_id, shown_name, truth_id, fast = sid, name, sid, True
            noise = rng.random()
            if noise < 0.08:
                shown_id = f" {sid.translate(_FULL_WIDTH)}"  # 全角数字 + 空格，可以还原
            elif noise < 0.12:
                shown_id = truth_id = f"TEST99{seat:03d}"  # 学号不存在
                fast = False
            elif noise < 0.16:
                shown_name, fast = f"测试学生{index}-{seat + 50:02d}", False  # 姓名不符
            elif noise < 0.20:
                text = " / ".join(reversed(text.split(" ")))  # 顺序颠倒、斜杠分隔，可以还原
            elif noise < 0.23:
                text, truth_code, fast = "优胜", None, False  # 无法确定等级，不应猜测
            declared: str | None = code
            roll = rng.random()
            if roll < 0.1:
                declared = rng.choice([c for c in codes if c != code])
                fast = False
            elif roll < 0.2:
                declared, fast = None, False
            if declared is not None:
                declarations.append(
                    {"id": next_declaration, "student_id": sid, "option_code": declared}
                )
                next_declaration += 1
            row = [str(seat), shown_id, shown_name, text, ""]
            rows.append(row)
            truth.append({"row": len(rows), "student_id": truth_id, "option_code": truth_code,
                          "fast_track": fast})  # fmt: skip
            if rng.random() < 0.03:  # 重复行
                rows.append([*row[:4], "重复"])
                truth.append({"row": len(rows), "student_id": truth_id,
                              "option_code": truth_code, "fast_track": False})  # fmt: skip
        cases.append(
            {
                "id": f"list{index}-{item}",
                "catalog_item": item,
                "context": context,
                "rows": rows,
                "students": students,
                "declarations": declarations,
                "truth": truth,
            }
        )
    return {"seed": seed, "synthetic": True, "cases": cases}
