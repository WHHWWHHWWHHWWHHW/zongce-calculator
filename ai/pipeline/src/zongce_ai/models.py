"""流水线的数据结构。分数与置信度一律用 Decimal（CLAUDE.md §10）。"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExtractedRecord(_Model):
    """表单中的一条记录（如获奖名单的一行）。"""

    row: int = Field(description="在表格中的行号（表头为第 1 行）")
    student_id: str
    name: str | None = None
    option_text: str = Field(description="用于判断等级的原文（如“省级 一等奖”）")
    option_code: str | None = Field(description="对应的申报目录选项；无法确定时为空")
    value: Decimal | None = Field(default=None, description="表单给出的分值（如有）")
    confidence: Decimal = Field(ge=0, le=1)
    issues: tuple[str, ...] = ()
    group: str = Field(default="", description="所属活动等分组；同一学生在不同活动中出现不算重复")
    unit_item: bool = Field(default=False, description="按次计分的项目，本来就没有选项")
    by_name: bool = Field(default=False, description="名单没有学号，按班级 + 姓名找的学生")


class TableExtraction(_Model):
    records: tuple[ExtractedRecord, ...]
    columns: dict[str, str] = Field(description="表头 → 用途（学号、姓名、等级、分值）")
    ignored_columns: tuple[str, ...] = ()
    skipped_rows: tuple[int, ...] = Field(default=(), description="学号为空而跳过的行号")
