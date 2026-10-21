"""学院各部门导出表：到梦空间学分汇总（按学号）、志愿章汇总（多个工作表，按班级 + 姓名）。

列的口径由负责人 2026-10-21 确定：“积分总和”即第二课堂积分，“总章数”即公益劳动次数。
"""

import io
from typing import Any

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from backend_helpers import API, World, make_user, upload, xlsx
from zongce_backend.models import Role


def _workbook(sheets: dict[str, list[list[Any]]]) -> bytes:
    workbook = Workbook()
    for sheet in list(workbook.worksheets):
        workbook.remove(sheet)
    for title, rows in sheets.items():
        sheet = workbook.create_sheet(title)
        for row in rows:
            sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _records(client: TestClient, world: World, username: str) -> dict[str, str]:
    rows = client.get(
        f"{API}/years/{world.year_id}/college-data", params={"username": username},
        headers=world.admin,
    ).json()  # fmt: skip
    return {r["field"]: r["value"] for r in rows}


def test_dream_space_credit_by_student_id(client: TestClient, world: World) -> None:
    table: list[list[Any]] = [
        ["ID", "姓名", "学号", "年级", "班级", "参与时长（分）", "创新实践课程学分-积分",
         "积分总和", "转换后学分总和"],
        [1, "测试TEST0002", "TEST0002", "2025", "测试A班", 300, 3.5, 3.5, 0],
    ]  # fmt: skip
    body = client.post(
        f"{API}/years/{world.year_id}/college-data/import",
        files=upload("学分汇总 2025级.xlsx", xlsx(table)), headers=world.admin,
    ).json()  # fmt: skip
    assert body["mapped_columns"] == {"积分总和": "second_classroom"}
    assert "姓名" not in body["ignored_columns"]
    assert "学号" not in body["ignored_columns"]
    assert "转换后学分总和" in body["ignored_columns"]
    assert _records(client, world, "TEST0002") == {"second_classroom": "3.5"}


def test_volunteer_badges_by_class_and_name(client: TestClient, world: World, db: Session) -> None:
    for username in ("TEST0201", "TEST0202"):
        user = make_user(db, username, Role.STUDENT, class_name="测试C班")
        user.name = "同 名"
    db.commit()
    header = ["班级", "姓名", "志愿汇转化章", "活动名称", "活动章数", "总章数"]
    data = _workbook(
        {
            "2025级": [
                header,
                ["测试A班", "测试TEST0002", 2, "迎新", 1, 3],
                [" 测试A班 ", "测试TEST0003", "", "", "", ""],  # 没有数值：不写入
                ["测试A班", "查无此人", 1, "", 0, 1],
                ["测试C班", "同名", 1, "", 0, 1],
            ],
            "2024级": [[*header, "", ""], ["测试B班", "测试TEST0101", 4, "", 2, 6]],
            "说明": [["本表由志愿者协会整理"]],
            "空表": [],
        }
    )
    body = client.post(
        f"{API}/years/{world.year_id}/college-data/import",
        files=upload("志愿章汇总.xlsx", data), headers=world.admin,
    ).json()  # fmt: skip
    assert body["mapped_columns"] == {"总章数": "public_service"}
    assert body["rows"] == 5
    assert body["changed"] == 2
    messages = [e["message"] for e in body["errors"]]
    assert messages == [
        "[说明] 表头缺少“学号”列（没有学号时，需要“班级”和“姓名”两列），已跳过该工作表",
        "[2025级] 按班级和姓名找不到学生：测试A班 查无此人",
        "[2025级] 测试C班 有 2 名同名学生 同名，请改用学号",
    ]
    assert _records(client, world, "TEST0002") == {"public_service": "3"}
    assert _records(client, world, "TEST0101") == {"public_service": "6"}
    assert _records(client, world, "TEST0003") == {}


def test_first_sheet_must_have_identity_and_some_sheet_scores(
    client: TestClient, world: World
) -> None:
    url = f"{API}/years/{world.year_id}/college-data/import"

    def post(sheets: dict[str, list[list[Any]]]) -> Any:
        return client.post(
            url, files=upload("x.xlsx", _workbook(sheets)), headers=world.admin
        ).json()

    first = post({"A": [["说明"]], "B": [["学号", "绩点"]]})
    assert first["error"]["message"].startswith("表头缺少“学号”列")
    no_scores = post({"A": [["班级", "姓名", "备注"]]})
    assert no_scores["error"]["message"] == "没有识别出任何成绩列，请检查表头"
    assert post({"A": []})["error"]["message"] == "表格为空"
