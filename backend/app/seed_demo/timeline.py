# -*- coding: utf-8 -*-
"""Demo 时间线：以参考日期为锚点的学期时钟（评审 1/2）。

设计：
- DEFAULT_REFERENCE_DATE = 2026-12-07（固定），--reference-date now 时取运行当日；
- 所有业务时间都是相对锚点的偏移（天），保证任意锚点下故事结构一致；
- 偏移常量按真实教学学期排布（开学 ref-91d 至 期末 ref+39d）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone


def _aware(d: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(d, time(hour, minute), tzinfo=timezone.utc)


@dataclass(frozen=True)
class DemoClock:
    """学期时钟：所有业务时间 = ref + 偏移（天）。"""

    ref: datetime

    @classmethod
    def from_reference_date(cls, reference_date: date) -> "DemoClock":
        return cls(_aware(reference_date, 10, 0))

    # ── 学期边界（评审 2） ─────────────────────────────────────────
    def term_start(self) -> datetime:
        return self.day(-91)  # 2026-09-07 开学

    def term_end(self) -> datetime:
        return self.day(39)  # 2027-01-15 期末

    def term_start_date(self) -> date:
        return self.term_start().date()

    def term_end_date(self) -> date:
        return self.term_end().date()

    # ── 基础时间点 ─────────────────────────────────────────────────
    def day(self, offset_days: int, hour: int = 10, minute: int = 0) -> datetime:
        return self.ref + timedelta(days=offset_days, hours=hour - self.ref.hour, minutes=minute - self.ref.minute)

    def course_published(self) -> datetime:
        return self.day(-93, 9)  # 2026-09-05 课程发布

    def enrollment_start(self) -> datetime:
        return self.day(-91, 9)  # 2026-09-07 选课开始

    def enrollment_end(self) -> datetime:
        return self.day(-87, 17)  # 2026-09-11 选课结束

    # ── 作业（唯一事实源：10 个作业，含 AI 评分） ────────────────────
    # (course_title, key, title, ai, publish_offset, due_offset)
    ASSIGNMENT_SPECS = [
        ("Python 与 AI 实验全流程", "hw1", "作业一：正数求和", False, -80, -66),
        ("Python 与 AI 实验全流程", "hw2", "作业二：括号匹配", False, -59, -45),
        ("Python 与 AI 实验全流程", "hw3", "作业三：二分查找", False, -42, -31),
        ("Python 与 AI 实验全流程", "ai1", "AI 评分作业一：缺失成绩填充", True, -24, -10),
        ("Python 与 AI 实验全流程", "ai2", "AI 评分作业二：向量标准化", True, -10, 4),
        ("Python 程序设计基础", "py1", "基础练习：变量与运算", False, -55, -40),
        ("Python 程序设计基础", "py2", "基础练习：列表操作", False, -32, -18),
        ("数据结构与算法实战", "ds1", "算法练习：递归求和", False, -50, -35),
        ("机器学习基础", "ml1", "机器学习：线性拟合预测", False, -22, -8),
        ("统计学习基础", "st1", "统计练习：均值与方差", False, -15, -2),
    ]

    def assignment_published(self, key: str) -> datetime:
        for _course, k, _title, _ai, pub, _due in self.ASSIGNMENT_SPECS:
            if k == key:
                return self.day(pub, 9)
        raise KeyError(key)

    def assignment_due(self, key: str) -> datetime:
        for _course, k, _title, _ai, _pub, due in self.ASSIGNMENT_SPECS:
            if k == key:
                return self.day(due, 23, 59)
        raise KeyError(key)

    # ── 考试 ───────────────────────────────────────────────────────
    def midterm_start(self) -> datetime:
        return self.day(-35, 9)  # 2026-11-02 09:00

    def midterm_end(self) -> datetime:
        return self.day(-31, 17)  # 2026-11-06 17:00

    def midterm_review_released(self) -> datetime:
        return self.day(-28, 10)  # 2026-11-09 成绩复核发布

    def final_published(self) -> datetime:
        return self.day(7, 9)  # 2026-12-14 期末发布

    def final_start(self) -> datetime:
        return self.day(35, 9)  # 2027-01-11 09:00

    def final_end(self) -> datetime:
        return self.day(39, 17)  # 2027-01-15 17:00

    def quiz_start(self) -> datetime:
        return self.day(-12, 9)  # 2026-11-25 章节测验

    def quiz_end(self) -> datetime:
        return self.day(-5, 17)  # 2026-12-02

    # ── 其他 ───────────────────────────────────────────────────────
    def new_student_joined(self) -> datetime:
        return self.day(-17, 10)  # 2026-11-20 新学生入学

    def experiment_activity_window(self) -> tuple[datetime, datetime]:
        return self.day(-60, 9), self.day(-2, 17)  # 10 月 ~ 12 月初
