"""生成合成演示数据（CLAUDE.md §11：仓库与测试只允许合成数据；学号以 TEST 开头，姓名为“测试学生”）。

用法（输出到已被 .gitignore 排除的 data/ 目录）：
    uv run python scripts/gen_fake_data.py --out data/demo --classes 2 --students 30 --seed 1

生成两个文件，可直接用管理员账号导入：
- users.xlsx：学号、姓名、班级、角色（每班第 1 名同时是班级审核员）
- college.xlsx：学号、学分绩点、第二课堂、公益劳动、体测成绩、宿舍成绩、思想品德四项（全班评议名单）

想一步生成完整的演示库（账号、申报、审核、核算、公示），用 `uv run zongce seed-demo`，
见 docs/本机运行.md。
"""

import argparse
from pathlib import Path

from zongce_backend.fake_data import college_rows, users_rows, write_xlsx


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
