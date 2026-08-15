# -*- coding: utf-8 -*-
"""Demo Seed 唯一事实源：固定种子、参考日期、账号、课程目录、题库、画像参数。

所有业务模块只从这里读取常量，保证同一代码版本 + 同一参考日期下产出完全一致。
"""
from __future__ import annotations

import os
from datetime import date

# ── 固定随机种子（评审 4：所有随机都从 DEMO_SEED + 实体稳定 key 派生） ──────────
DEMO_SEED = 20260815

# ── 固定参考日期（评审 1：默认固定，任何时刻运行产出一致） ─────────────────────
# 2026-12-07（第 14 周周一）：学期中后段，期中已结束、期末已发布、AI 作业临近截止。
DEFAULT_REFERENCE_DATE = date(2026, 12, 7)

# ── 演示账号密码（env 可覆盖） ────────────────────────────────────────────────
# 密码规则：>=8 字符、非全空白、不等于用户名。Demo1234! 满足全部规则。
DEFAULT_PASSWORD = "Demo1234!"


def demo_password() -> str:
    return os.environ.get("DAI_DEMO_PASSWORD", DEFAULT_PASSWORD)


# ── 固定演示账号（评审 7：不占用 admin/teacher/student，与 E2E 完全隔离） ──────
ADMIN_USERNAME = "demo_admin"
ADMIN_REAL_NAME = "系统管理员"
DEVELOPER_USERNAME = "demo_developer"
DEVELOPER_REAL_NAME = "实验平台开发者"

# (username, real_name) —— 教师固定账号
TEACHER_DEFS = [
    ("teacher_zhang", "张明远"),
    ("teacher_chen", "陈思远"),
    ("teacher_zhao", "赵清禾"),
]

# 固定画像学生：username, real_name, archetype（画像 key，见 ARCHETYPES）
FIXED_STUDENT_DEFS = [
    ("demo_student_elite", "林书瑶", "elite"),
    ("demo_student_average", "周子涵", "average"),
    ("demo_student_struggling", "王雨桐", "struggling"),
    ("demo_student_new", "赵晨曦", "new"),
]

# 背景学生学号前缀（教学班 code 与学号共用）
CLASS_PREFIXES = [f"246216{i:02d}" for i in range(1, 7)]  # 24621601..24621606
# 每个教学班 10 人；画像学生各占一班一个名额（班1..班4），背景学生补齐
CLASS_SIZE = 10
BACKGROUND_CLASS_MEMBERSHIP = {
    0: 9,  # 班1：elite + 9 背景
    1: 9,  # 班2：average + 9 背景
    2: 9,  # 班3：struggling + 9 背景
    3: 9,  # 班4：new + 9 背景
    4: 10,  # 班5：10 背景
    5: 10,  # 班6：10 背景
}
BACKGROUND_TOTAL = sum(BACKGROUND_CLASS_MEMBERSHIP.values())  # 56


def background_usernames() -> list[str]:
    """稳定生成 56 个背景学生用户名：student_246216XX_YY（XX=班号，YY=班内序号）。"""
    result: list[str] = []
    for class_index, prefix in enumerate(CLASS_PREFIXES):
        count = BACKGROUND_CLASS_MEMBERSHIP[class_index]
        # 班内序号从 1 开始；班1..班4 的序号 1 留给画像学生，背景从 2 开始
        start = 2 if class_index < 4 else 1
        for offset in range(count):
            seq = start + offset
            result.append(f"student_{prefix}_{seq:02d}")
    return result


# ── 学期（评审 2：真实教学学期） ──────────────────────────────────────────────
ACTIVE_TERM = {
    "code": "2026-2027-1",
    "name": "2026-2027 学年第一学期（秋季）",
    "status": "active",
}
CLOSED_TERM = {
    "code": "2025-2026-2",
    "name": "2025-2026 学年第二学期（春季）",
    "status": "closed",
}

# ── 课程目录：title, teacher_key, env_slug, status, visibility, chapters ─────
# flagship: 旗舰全链路课程；其余为支撑课程（评审 2/7）
FLAGSHIP_COURSE_TITLE = "Python 与 AI 实验全流程"

COURSE_CATALOG = [
    # (title, teacher_key, env_slug, status, chapter_topics)
    (FLAGSHIP_COURSE_TITLE, "teacher_zhang", "basic", "published",
     ["Python 基础与函数", "列表、字典与集合", "排序与查找算法", "数据处理与可视化", "机器学习入门", "综合实验与项目"]),
    ("Python 程序设计基础", "teacher_zhang", "basic", "published",
     ["变量与数据类型", "流程控制", "函数与模块"]),
    ("数据结构与算法实战", "teacher_zhang", "basic", "published",
     ["线性表与栈", "递归与分治"]),
    ("数据处理与可视化", "teacher_chen", "data", "published",
     ["NumPy 科学计算", "Pandas 数据清洗"]),
    ("机器学习基础", "teacher_chen", "data", "published",
     ["线性模型", "模型评估"]),
    ("统计学习基础", "teacher_chen", "basic", "published",
     ["描述统计", "假设检验"]),
    ("Web API 开发入门", "teacher_zhao", "basic", "draft",
     ["HTTP 与 REST", "FastAPI 基础"]),
]

# 各课程绑定的教学班（0-based 班索引；旗舰绑全部 6 班）
COURSE_CLASSES = {
    FLAGSHIP_COURSE_TITLE: list(range(6)),
    "Python 程序设计基础": [0, 1, 2],
    "数据结构与算法实战": [2, 3],
    "数据处理与可视化": [1, 2, 3],
    "机器学习基础": [2, 3, 4],
    "统计学习基础": [0, 4, 5],
    "Web API 开发入门": [0],
}

# ── 画像参数（评审 2.5：让统计页面表现真实差异） ─────────────────────────────
# 每个画像：提交率、基础分数区间、重交概率、AI 复核概率、缺交作业数、实验完成度
ARCHETYPES = {
    "elite": {
        "submit_rate": 1.0, "score_lo": 90, "score_hi": 100,
        "retry_prob": 0.1, "review_prob": 0.02, "missing_assignments": 0,
        "lesson_complete": 1.0, "experiment_level": 3,  # 3=全部完成并提交
    },
    "average": {
        "submit_rate": 0.85, "score_lo": 65, "score_hi": 88,
        "retry_prob": 0.35, "review_prob": 0.12, "missing_assignments": 1,
        "lesson_complete": 0.75, "experiment_level": 2,  # 2=提交未复核/部分
    },
    "struggling": {
        "submit_rate": 0.6, "score_lo": 15, "score_hi": 55,
        "retry_prob": 0.8, "review_prob": 0.55, "missing_assignments": 2,
        "lesson_complete": 0.4, "experiment_level": 1,  # 1=started
    },
    "new": {
        "submit_rate": 0.3, "score_lo": 50, "score_hi": 80,
        "retry_prob": 0.4, "review_prob": 0.2, "missing_assignments": 4,
        "lesson_complete": 0.2, "experiment_level": 1,
    },
}
# 背景学生统一按 average 分布（用 make_rng 按用户名派生个体差异）
BACKGROUND_ARCHETYPE = "average"
