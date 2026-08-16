# -*- coding: utf-8 -*-
"""Demo 数据体系入口（评审 3.3/3.4）。

入口：python -m app.cli seed-demo [--reset-demo] [--reference-date now|YYYY-MM-DD]
      [--skip-env-check] [--force-fixture]

幂等：所有实体 get_or_create，二次运行产出一致；随机源 make_rng 按实体稳定 key 派生。
所有权：demo_seed_marks 登记；--reset-demo 只删登记数据。
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import EnvironmentVersion

from .cleanup import reset_demo_data
from .constants import DEFAULT_REFERENCE_DATE
from .marks import ensure_marks_table
from .timeline import DemoClock
from .verify import verify_demo_data

logger = logging.getLogger("dai.seed_demo")

MODULES = ["users", "courses", "experiments", "assignments", "ai_grading", "exams", "announcements"]


def resolve_reference_date(value: str | None) -> date:
    """解析 --reference-date：now -> 今天；YYYY-MM-DD -> 钉死；None -> 固定默认。"""
    if value is None:
        return DEFAULT_REFERENCE_DATE
    if value.strip().lower() in ("now", "today"):
        return datetime.now().date()
    return date.fromisoformat(value.strip())


def resolve_environments(db: Session, skip_env_check: bool = False) -> dict[str, EnvironmentVersion]:
    """解析可用的环境版本；basic 缺失时（除非跳过校验）报错退出，绝不伪造 digest。"""
    from app.services.environment_service import current_available_version

    basic = current_available_version(db, "basic")
    if basic is None and not skip_env_check:
        raise SystemExit(
            "Demo Seed 前置校验失败：basic 档位没有 available 且带 image_digest 的版本。\n"
            "请先执行：python -m app.cli seed-environments --enqueue 并启动环境构建 Worker，"
            "或使用 scripts/seed-basic-environment-mysql.py 完成一次性初始化。"
        )
    data = current_available_version(db, "data")
    return {"basic": basic, "data": data}


def run_demo_seed(
    db: Session,
    *,
    reference_date: str | None = None,
    reset: bool = False,
    skip_env_check: bool = False,
    force_fixture: bool = False,
    run_verify: bool = True,
) -> dict:
    """执行 Demo 播种；返回汇总计数。"""
    if reset:
        logger.info("== [reset-demo] 清理既有 Demo 数据 ==")
        reset_demo_data(db)

    ensure_marks_table(db)
    clock = DemoClock.from_reference_date(resolve_reference_date(reference_date))
    logger.info("== Demo Seed 启动：参考日期 %s，种子 %s ==", clock.ref.date(), "20260815")

    # 0. 环境解析（前置校验）
    env_by_slug = resolve_environments(db, skip_env_check=skip_env_check)
    logger.info("环境：basic=%s data=%s", env_by_slug["basic"].id if env_by_slug["basic"] else None,
                env_by_slug["data"].id if env_by_slug["data"] else None)

    # 1. 用户 / 学期 / 教学班
    from . import users as users_mod
    user_map = users_mod.create_users(db, clock)
    academics = users_mod.create_academics(db, clock, user_map)
    user_map["_term"] = academics["term"]

    # 2. 课程 / 章节 / 课时 / 进度
    from . import courses as courses_mod
    courses = courses_mod.create_courses(db, clock, user_map, academics["term"])
    users_mod.link_courses_to_classes(db, courses, academics["classes"])
    courses_mod.create_course_whitelists(db, user_map, courses)
    courses_mod.create_lesson_progress(db, clock, user_map, courses)

    # 3. 实验模板 / 模块 / 记录 / 提交
    from . import experiments as experiments_mod
    experiments = experiments_mod.create_experiments(db, clock, user_map, env_by_slug)
    experiments_mod.create_experiment_records(db, clock, user_map, experiments, courses)

    # 4. 作业 / 题目 / 提交（真实判题优先 + Fixture 降级）
    from . import assignments as assignments_mod
    from .judge_real import real_judge_available
    ai_questions: list = []
    assignments_map, questions_by_key = assignments_mod.create_assignments_and_questions(
        db, clock, user_map, courses, env_by_slug, ai_questions,
    )
    use_real = False
    if not force_fixture:
        ok, reason = real_judge_available(db)
        if ok:
            use_real = True
            logger.info("真实判题可用：核心演示链将运行真实 Docker 判题")
        else:
            logger.warning("真实判题不可用（%s），全部提交降级为 seed_fixture", reason)
    sub_count = assignments_mod.create_submissions(
        db, clock, user_map, assignments_map, questions_by_key,
        env_by_slug["basic"], use_real_judge=use_real,
    )

    # 5. AI 评分（Rubric + CodeGrade 确定性 Fixture）
    from . import ai_grading as ai_mod
    cg_count = ai_mod.create_assignment_ai_grades(db, clock, user_map, ai_questions)

    # 6. 考试（考试 + 题目 + 提交 + 答案 + 成绩）
    from . import exams as exams_mod
    exams = exams_mod.create_exams(db, clock, user_map, courses)
    exams_mod.create_exam_submissions(db, clock, user_map, exams)
    cg_count += ai_mod.create_exam_ai_grades(db, clock, user_map, exams)

    # 7. 公告 + 已读
    from . import announcements as ann_mod
    ann_mod.create_announcements(db, clock, user_map, courses, exams)

    db.commit()

    # 8. 校验
    summary = {}
    if run_verify:
        summary = verify_demo_data(db)
        logger.info("== Demo Seed 完成：submissions=%s code_grades=%s ==", sub_count, cg_count)
    return {"submissions": sub_count, "code_grades": cg_count, **summary}
