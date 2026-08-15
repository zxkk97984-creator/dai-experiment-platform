# -*- coding: utf-8 -*-
"""作业 / 判题题目 / 提交与判题结果（评审 5：真实判题优先 + Fixture 降级）。

- 核心演示链（旗舰课程 legacy 判题作业 x 固定画像学生）优先真实 Docker 判题；
- 背景/历史数据为显式 seed_fixture Fixture（result_details 带 seed_fixture 标记，
  结构遵循 worker 输出格式 groups/system_errors/f_score/r_score）；
- 环境绑定全部使用 basic 档位真实可用版本（不伪造 digest）。
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    Course,
    EnvironmentVersion,
    JudgeQuestion,
    Submission,
    User,
)

from .constants import (
    ARCHETYPES,
    BACKGROUND_ARCHETYPE,
    COURSE_CATALOG,
    FIXED_STUDENT_DEFS,
    FLAGSHIP_COURSE_TITLE,
)
from .judge_real import judge_submission_real
from .marks import mark
from .rng import make_rng
from .tasks import AI_ROBUSTNESS_TESTS, BASIC_TASKS, DATA_TASKS
from .timeline import DemoClock

logger = logging.getLogger("dai.seed_demo.assignments")

# 作业定义唯一事实源在 timeline.DemoClock.ASSIGNMENT_SPECS
# (course_title, key, title, ai, publish_offset, due_offset)
ASSIGNMENT_DEFS = DemoClock.ASSIGNMENT_SPECS
# 普通任务索引：ai=True 用 DATA_TASKS，否则轮换 BASIC_TASKS
_TASK_INDEX = {key: idx for idx, key in enumerate(["hw1", "hw2", "hw3", "py1", "py2", "ds1", "ml1", "st1"])}


def _task_for(ai: bool, task_index: int) -> dict:
    """按定义取任务：AI 作业用 DATA_TASKS，普通作业轮换 BASIC_TASKS。"""
    if ai:
        return DATA_TASKS[task_index % len(DATA_TASKS)]
    return BASIC_TASKS[task_index % len(BASIC_TASKS)]


def course_teacher_key(course_title: str) -> str:
    for title, teacher_key, _env, _status, _topics in COURSE_CATALOG:
        if title == course_title:
            return teacher_key
    return "teacher_zhang"


def create_assignments_and_questions(
    db: Session, clock: DemoClock, users: dict, courses: dict,
    env_by_slug: dict, ai_enabled_questions: list,
):
    """创建作业与判题题目。

    返回 (assignments_by_course, questions_by_key)：
    - assignments_by_course: {course_title: {key: Assignment}}
    - questions_by_key: {(course_title, key): JudgeQuestion}（每题取第一个题目）
    """
    env = env_by_slug["basic"]
    assignments_by_course: dict[str, dict[str, Assignment]] = {}
    questions_by_key: dict = {}

    for (course_title, key, title, ai, _pub, _due) in ASSIGNMENT_DEFS:
        course = courses[course_title]
        task = _task_for(ai, _TASK_INDEX.get(key, 0))

        assignment = db.scalar(
            select(Assignment).where(
                Assignment.course_id == course.id,
                Assignment.title == title,
            )
        )
        if assignment is None:
            assignment = Assignment(
                course_id=course.id,
                title=title,
                description=(
                    f"【AI 评分作业】{task['description']}"
                    if ai else task["description"]
                ),
                status="published",
                due_at=clock.assignment_due(key),
                published_at=clock.assignment_published(key),
                created_by_id=users[course_teacher_key(course_title)].id,
                environment_version_id=env.id,
                import_policy_mode="restricted",
                allowed_imports=["pytest"],
            )
            db.add(assignment)
            db.flush()
            logger.info("[创建] 作业 %s", title)
        else:
            assignment.status = "published"
            assignment.due_at = clock.assignment_due(key)
            assignment.published_at = clock.assignment_published(key)
            assignment.environment_version_id = env.id
            db.flush()
            logger.info("[更新] 作业 %s", title)
        mark(db, "assignments", assignment.id)
        assignments_by_course.setdefault(course_title, {})[key] = assignment

        # 题目：AI 作业 1 题；普通作业 1-2 题
        q_count = 1 if ai else (1 if _TASK_INDEX.get(key, 0) % 3 == 0 else 2)
        for q_index in range(q_count):
            q_task = _task_for(ai, _TASK_INDEX.get(key, 0) + q_index)
            q_title = f"{title} - {q_task['title']}" if q_count > 1 else title
            question = db.scalar(
                select(JudgeQuestion).where(
                    JudgeQuestion.assignment_id == assignment.id,
                    JudgeQuestion.title == q_title,
                )
            )
            if question is None:
                kwargs = dict(
                    assignment_id=assignment.id,
                    title=q_title,
                    description=q_task["description"],
                    function_name=q_task["function_name"],
                    signature=q_task["signature"],
                    starter_code=q_task["starter"],
                    public_cases=q_task["cases"],
                    hidden_tests=q_task["hidden"],
                    time_limit_ms=10000,
                    memory_limit_mb=256,
                    max_attempts=5,
                    environment_version_id=None,  # 继承作业默认
                    import_policy_mode="inherit",
                    allowed_imports=[],
                )
                if ai:
                    kwargs["grading_mode"] = "active"
                    kwargs["teacher_constraints"] = {
                        "require_function": q_task["function_name"],
                        "seed_ai_demo": True,
                    }
                    kwargs["reference_solution"] = q_task["solution"]
                    kwargs["test_groups"] = _ai_test_groups(q_task)
                    kwargs["score_cap_rules"] = [
                        {"id": "CAP1", "condition_code": "off_topic", "cap": 0,
                         "description": "明显偏离题意时总分上限为 0"},
                        {"id": "CAP2", "condition_code": "hardcoded_public_examples", "cap": 20,
                         "description": "硬编码公开样例时总分上限为 20"},
                    ]
                question = JudgeQuestion(**kwargs)
                db.add(question)
                db.flush()
                logger.info("[创建] 题目 %s", q_title)
            else:
                if ai:
                    question.grading_mode = "active"
                db.flush()
            mark(db, "judge_questions", question.id)
            if ai:
                ai_enabled_questions.append(question)
            if (course_title, key) not in questions_by_key:
                questions_by_key[(course_title, key)] = question
    db.flush()
    return assignments_by_course, questions_by_key


def _ai_test_groups(task: dict) -> list[dict]:
    robustness = AI_ROBUSTNESS_TESTS.get(
        task["function_name"], "def test_robustness():\n    assert True\n"
    )
    return [
        {
            "id": "F1",
            "name": "功能正确性",
            "dimension": "F",
            "max_score": 60,
            "tests": task["hidden"],
        },
        {
            "id": "R1",
            "name": "鲁棒性与边界",
            "dimension": "R",
            "max_score": 10,
            "tests": robustness,
        },
    ]


def create_submissions(
    db: Session, clock: DemoClock, users: dict, assignments_by_course: dict,
    questions_by_key: dict, env: EnvironmentVersion, use_real_judge: bool,
) -> int:
    """为作业创建提交与判题结果；返回创建的提交数。"""
    students: list[User] = users["students"]
    archetype_map = {uname: a for uname, _n, a in FIXED_STUDENT_DEFS}
    total = 0

    for (course_title, key), question in questions_by_key.items():
        assignment = assignments_by_course[course_title][key]
        ai = question.grading_mode == "active"
        for student in students:
            archetype = archetype_map.get(student.username, BACKGROUND_ARCHETYPE)
            profile = ARCHETYPES[archetype]
            rng = make_rng("submission", student.username, question.title)

            submit_rate = profile["submit_rate"]
            if ai and archetype == BACKGROUND_ARCHETYPE:
                submit_rate = min(submit_rate, 0.6)
            if rng.random() > submit_rate:
                continue

            # 缺交控制：按画像 missing_assignments 比例随机跳过
            missing = profile["missing_assignments"]
            if missing and rng.random() < missing / 10.0:
                continue

            # 尝试次数：困难学生多次修改
            attempts = 1
            if archetype == "struggling":
                attempts = rng.randint(2, 3)
            elif archetype == "average":
                attempts = rng.randint(1, 2)

            for attempt in range(1, attempts + 1):
                existing = db.scalar(
                    select(Submission).where(
                        Submission.question_id == question.id,
                        Submission.student_id == student.id,
                        Submission.attempt_count == attempt - 1,
                    )
                )
                if existing is not None:
                    mark(db, "submissions", existing.id)
                    total += 1
                    continue

                is_final = attempt == attempts
                if is_final:
                    pass_prob = (profile["score_lo"] + profile["score_hi"]) / 200.0
                    wrong = rng.random() > pass_prob
                else:
                    wrong = True  # 前几次尝试是错的
                code, outcome = _student_code(question, wrong, rng)

                submitted_at = _submission_time(clock, rng, key)

                sub = Submission(
                    question_id=question.id,
                    student_id=student.id,
                    code=code,
                    status="queued",
                    grading_status="pending",
                    attempt_count=attempt - 1,
                    environment_version_id=env.id,
                    import_policy_mode_snapshot="restricted",
                    allowed_imports_snapshot=["pytest"],
                )
                db.add(sub)
                db.flush()
                mark(db, "submissions", sub.id)

                judged = False
                # 真实判题：仅 legacy 题目 + 固定画像学生（elite/average）。
                # 注意：背景学生 archetype 也取 "average"，必须用 username in
                # archetype_map 限定在 4 个固定学生内，否则 56 个背景学生也会
                # 触发真实判题（上次技术债：525 条 system_error 的来源之一）。
                if (
                    use_real_judge and not ai
                    and student.username in archetype_map
                    and archetype in ("elite", "average")
                ):
                    judged = judge_submission_real(db, sub, question)
                if not judged:
                    _fixture_judge_result(sub, outcome, rng, submitted_at)
                total += 1
    db.flush()
    return total


def task_for_question(question: JudgeQuestion) -> dict:
    """从题目字段反查任务字典（用于 Fixture 生成代码）。"""
    for task in BASIC_TASKS + DATA_TASKS:
        if task["function_name"] == question.function_name:
            return task
    return BASIC_TASKS[0]


def _student_code(question: JudgeQuestion, wrong: bool, rng):
    """生成学生代码：正确=参考答案；错误=含缺陷的变体。"""
    task = task_for_question(question)
    if not wrong:
        return task["solution"], "accepted"
    variants = [
        (task["starter"] + "\n    return 0", "wrong_answer"),
        ("def " + task["function_name"] + "(*args):\n    return None", "wrong_answer"),
        (task["solution"].replace("return ", "return None # TODO "), "wrong_answer"),
    ]
    return rng.choice(variants)


def _submission_time(clock: DemoClock, rng, key: str):
    """提交时间：发布后、截止前 3 天内集中。"""
    from datetime import timedelta as _td

    published = clock.assignment_published(key)
    due = clock.assignment_due(key)
    span = (due - published).total_seconds()
    t = published + _td(seconds=rng.uniform(0, span))
    # 60% 概率落在截止前 3 天
    if rng.random() < 0.6:
        window = min(_td(days=3), due - published)
        t = due - _td(seconds=rng.uniform(0, window.total_seconds()))
    return t


def _fixture_judge_result(sub: Submission, outcome: str, rng, submitted_at):
    """Fixture 判题结果：结构遵循 worker 输出（seed_fixture 显式标记）。"""
    from datetime import timedelta as _td

    from app.services.deterministic_scoring import calculate_group_score

    if outcome == "accepted":
        counts = {"passed": 3, "failed": 0, "errors": 0, "skipped": 0}
    else:
        passed = rng.randint(0, 1)
        counts = {"passed": passed, "failed": 3 - passed, "errors": 0, "skipped": 0}
    f_score = calculate_group_score(60, counts)
    r_score = calculate_group_score(10, counts)
    sub.status = "accepted" if outcome == "accepted" else "wrong_answer"
    sub.score = 100.0 if outcome == "accepted" else round(f_score + r_score, 4)
    sub.grading_status = "completed"
    sub.finished_at = submitted_at + _td(minutes=rng.randint(1, 30))
    sub.execution_time_ms = rng.randint(5, 300)
    sub.result_details = {
        "groups": [
            {"id": "F1", "name": "功能正确性", "dimension": "F", "max_score": 60,
             "score": f_score, "counts": counts},
        ],
        "system_errors": [],
        "f_score": f_score,
        "r_score": r_score,
        "seed_fixture": True,
    }