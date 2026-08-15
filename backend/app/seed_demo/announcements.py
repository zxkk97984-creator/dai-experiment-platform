# -*- coding: utf-8 -*-
"""公告 + 已读回执。"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Announcement, AnnouncementRead, User

from .marks import mark
from .timeline import DemoClock

logger = logging.getLogger("dai.seed_demo.announcements")

# (title, content, priority, scope, course_key_or_None, publish_offset, expires_offset)
ANNOUNCEMENT_DEFS = [
    ("新学期开学通知", "新学期开始，欢迎同学们选课学习。请于开学两周内完成课程选课。",
     "normal", "global", None, -93, -30),
    ("期中考试安排", "期中测验将于第 9 周进行，请提前复习函数与数据结构章节。",
     "important", "course", "midterm", -38, -20),
    ("AI 评分功能上线说明", "作业与考试编程题已接入 AI 智能评分，评分结果可查看分项得分与改进建议。",
     "normal", "course", "midterm", -25, 10),
    ("期末上机考试安排", "期末上机考试将于学期最后一周进行，涵盖 Python 与 AI 综合内容。",
     "important", "global", None, 7, 40),
    ("章节测验提醒", "《机器学习基础》章节测验已开放，请在本周内完成。",
     "normal", "course", "quiz", -12, -3),
]


def create_announcements(
    db: Session, clock: DemoClock, users: dict, courses: dict, exams: dict,
) -> None:
    """创建公告与已读回执。"""
    admin = users["demo_admin"]
    teacher_zhang = users["teacher_zhang"]
    teacher_chen = users["teacher_chen"]

    for (title, content, priority, scope, ref_key, pub_offset, exp_offset) in ANNOUNCEMENT_DEFS:
        if scope == "course":
            if ref_key == "midterm":
                course = courses["Python 与 AI 实验全流程"]
                author = teacher_zhang
            else:
                course = courses.get("机器学习基础")
                author = teacher_chen
            course_id = course.id if course else None
            author_id = author.id
        else:
            course_id = None
            author_id = admin.id

        ann = db.scalar(
            select(Announcement).where(
                Announcement.title == title,
                Announcement.author_id == author_id,
            )
        )
        if ann is None:
            ann = Announcement(
                title=title,
                content=content,
                priority=priority,
                scope=scope,
                course_id=course_id,
                author_id=author_id,
                published_at=clock.day(pub_offset, 9),
                expires_at=clock.day(exp_offset, 23, 59) if exp_offset else None,
            )
            db.add(ann)
            db.flush()
            logger.info("[创建] 公告 %s", title)
        else:
            ann.content = content
            ann.priority = priority
            ann.scope = scope
            ann.course_id = course_id
            ann.author_id = author_id
            ann.published_at = clock.day(pub_offset, 9)
            ann.expires_at = clock.day(exp_offset, 23, 59) if exp_offset else None
            db.flush()
            logger.info("[更新] 公告 %s", title)
        mark(db, "announcements", ann.id)

        # 已读回执：固定学生全部已读；背景学生前 20 人已读
        read_students = [u for u in users["students"] if not u.username.startswith("student_")] +                         [u for u in users["students"] if u.username.startswith("student_")][:20]
        for student in read_students:
            existing = db.scalar(
                select(AnnouncementRead).where(
                    AnnouncementRead.announcement_id == ann.id,
                    AnnouncementRead.user_id == student.id,
                )
            )
            if existing is not None:
                mark(db, "announcement_reads", existing.id)
                continue
            row = AnnouncementRead(
                announcement_id=ann.id,
                user_id=student.id,
                read_at=ann.published_at + __import__("datetime").timedelta(hours=1),
            )
            db.add(row)
            db.flush()
            mark(db, "announcement_reads", row.id)
    db.flush()
