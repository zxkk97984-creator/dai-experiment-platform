"""AI 评分编排——支持 Submission 和 ExamAnswer，应用上限、防重复、折算"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import CodeGrade, ExamAnswer, ExamQuestion, JudgeQuestion, QuestionRubric, Submission
from app.schemas.ai_grading import AIGradeResponse
from app.services.ai_client import DeepSeekClient
from app.services.ai_prompts import build_grading_messages
from app.services.ai_score_validation import detect_cross_dimension_duplicates, validate_ai_output
from app.services.score_merger import merge_scores
from app.services.static_analysis import analyze_python

logger = logging.getLogger("dai.ai_grader")


def grade_code_submission(
    db: Session,
    client: DeepSeekClient,
    code_grade_id: int,
) -> CodeGrade:
    """编排单份 AI 代码评分——同时支持 Submission 和 ExamAnswer"""
    grade = db.get(CodeGrade, code_grade_id)
    if grade is None:
        raise ValueError(f"CodeGrade {code_grade_id} 不存在")

    rubric = db.get(QuestionRubric, grade.rubric_id)
    if rubric is None:
        raise ValueError(f"Rubric {grade.rubric_id} 不存在")

    # 确定目标类型
    if grade.submission_id:
        submission = db.get(Submission, grade.submission_id)
        question = submission.question if submission else None
        code = submission.code if submission else ""
        target_id = grade.submission_id
        target_type = "submission"
    elif grade.exam_answer_id:
        answer = db.get(ExamAnswer, grade.exam_answer_id)
        question = answer.question if answer else None
        code = answer.code_answer or ""
        target_id = grade.exam_answer_id
        target_type = "exam_answer"
    else:
        raise ValueError("CodeGrade 未关联任何提交")

    if question is None:
        raise ValueError("题目不存在")

    # 静态分析
    static = analyze_python(code)

    # 构建评分请求
    deterministic = {
        "functional_score": grade.functional_score,
        "robustness_score": grade.robustness_score,
        "details": grade.deterministic_details,
    }

    messages = build_grading_messages(
        rubric=rubric.rubric_json,
        question={
            "title": question.title if hasattr(question, "title") else question.prompt,
            "description": getattr(question, "description", getattr(question, "prompt", None)),
            "function_name": getattr(question, "function_name", getattr(question, "prompt", None)),
        },
        code=code,
        deterministic=deterministic,
        static_analysis=static,
        rubric_version=rubric.version,
    )

    # 调用 AI
    raw_response = client.chat_json(messages)
    raw_json_str = json.dumps(raw_response, ensure_ascii=False)

    # Pydantic 校验
    ai_result = AIGradeResponse.model_validate(raw_response)

    # 业务校验
    code_lines = list(range(1, len(code.splitlines()) + 1))
    validation_errors = validate_ai_output(
        rubric={
            "rubric_version": rubric.version,
            "algorithm_criteria": rubric.rubric_json.get("algorithm_criteria", []),
        },
        ai_result=ai_result.model_dump(),
        code_lines=code_lines,
    )

    # 防重复扣分
    a_items = [item.model_dump() for item in ai_result.algorithm.items]
    q_items = [item.model_dump() for item in ai_result.code_quality.items]
    duplicates = detect_cross_dimension_duplicates(a_items, q_items)
    if duplicates:
        for d in duplicates:
            validation_errors.append(
                f"跨维度重复扣分: A.{d['a_criterion']} 与 Q.{d['q_criterion']} reason={d['reason_code']}"
            )

    # 应用题目上限规则
    cap = None
    if grade.submission_id:
        q = submission.question if submission else None
    else:
        q = question
    caps_from_teacher = getattr(q, "score_cap_rules", []) if q else []
    ai_cap_ids = set(ai_result.triggered_cap_rule_ids)
    for rule in caps_from_teacher:
        if rule.get("id") in ai_cap_ids:
            rule_cap = float(rule.get("cap", 100))
            cap = min(cap, rule_cap) if cap is not None else rule_cap

    # 后端合分
    exam_points = None
    if target_type == "exam_answer" and isinstance(question, ExamQuestion):
        exam_points = question.points

    merged = merge_scores(
        f=grade.functional_score,
        a=ai_result.algorithm.dimension_score,
        r=grade.robustness_score,
        q=ai_result.code_quality.dimension_score,
        cap=cap,
        exam_points=exam_points,
    )

    # 保存结果
    grade.algorithm_score = ai_result.algorithm.dimension_score
    grade.quality_score = ai_result.code_quality.dimension_score
    grade.raw_total = merged.raw_total
    grade.score_cap = cap
    grade.final_score_100 = merged.final_score_100
    grade.scaled_score = merged.scaled_score
    grade.ai_result = ai_result.model_dump()
    grade.raw_response = raw_json_str
    grade.static_analysis = static
    grade.needs_teacher_review = ai_result.needs_teacher_review or len(validation_errors) > 0
    if grade.needs_teacher_review:
        grade.review_reason = "; ".join(validation_errors) if validation_errors else ai_result.review_reason
        grade.status = "review_required"

    # active 模式更新正式分，shadow 保持旧分
    if grade.mode == "active" and not grade.needs_teacher_review:
        if grade.submission_id:
            sub = db.get(Submission, grade.submission_id)
            if sub:
                sub.score = merged.final_score_100
                sub.status = "graded"
        elif grade.exam_answer_id:
            ans = db.get(ExamAnswer, grade.exam_answer_id)
            if ans and isinstance(question, ExamQuestion):
                ans.score = merged.scaled_score
                # 不在此处 finalize——由 process_ai_grade 完成后再触发

    db.flush()

    logger.info(
        "ai_grade_completed",
        extra={
            "grade_id": code_grade_id,
            "mode": grade.mode,
            "raw_total": merged.raw_total,
            "final_score": merged.final_score_100,
        },
    )
    return grade
