"""AI 评分编排——单份提交的完整评分流程"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import CodeGrade, QuestionRubric, Submission
from app.schemas.ai_grading import AIGradeResponse
from app.services.ai_client import DeepSeekClient
from app.services.ai_prompts import build_grading_messages
from app.services.ai_score_validation import validate_ai_output
from app.services.score_merger import merge_scores
from app.services.static_analysis import analyze_python

logger = logging.getLogger("dai.ai_grader")


def grade_submission_code(
    db: Session,
    client: DeepSeekClient,
    code_grade_id: int,
) -> CodeGrade:
    """编排单份 AI 代码评分全流程"""
    grade = db.get(CodeGrade, code_grade_id)
    if grade is None:
        raise ValueError(f"CodeGrade {code_grade_id} 不存在")

    # 1. 读取关联数据
    rubric = db.get(QuestionRubric, grade.rubric_id)
    if rubric is None:
        raise ValueError(f"Rubric {grade.rubric_id} 不存在")

    submission = db.get(Submission, grade.submission_id)
    if submission is None:
        raise ValueError(f"Submission {grade.submission_id} 不存在")

    # 2. 获取题目信息（通过 submission → question）
    question = submission.question

    # 3. 运行静态分析
    static = analyze_python(submission.code)

    # 4. 构建评分请求
    deterministic = {
        "functional_score": grade.functional_score,
        "robustness_score": grade.robustness_score,
        "details": grade.deterministic_details,
    }

    messages = build_grading_messages(
        rubric=rubric.rubric_json,
        question={
            "title": question.title,
            "description": getattr(question, "description", None),
            "function_name": question.function_name,
        },
        code=submission.code,
        deterministic=deterministic,
        static_analysis=static,
    )

    # 5. 调用 AI（支持一次修复重试）
    raw_response = client.chat_json(messages)
    raw_json_str = json.dumps(raw_response, ensure_ascii=False)

    # 6. Pydantic 校验
    ai_result = AIGradeResponse.model_validate(raw_response)

    # 7. 业务校验
    code_lines = list(range(1, len(submission.code.splitlines()) + 1))
    validation_errors = validate_ai_output(
        rubric={"rubric_version": rubric.version, "algorithm_criteria": rubric.rubric_json.get("algorithm_criteria", [])},
        ai_result=ai_result.model_dump(),
        code_lines=code_lines,
    )

    # 8. 后端合分
    merged = merge_scores(
        f=grade.functional_score,
        a=ai_result.algorithm.dimension_score,
        r=grade.robustness_score,
        q=ai_result.code_quality.dimension_score,
        cap=None,  # 上限由调用方在保存前决定
        exam_points=None,
    )

    # 9. 保存结果
    grade.algorithm_score = ai_result.algorithm.dimension_score
    grade.quality_score = ai_result.code_quality.dimension_score
    grade.raw_total = merged.raw_total
    grade.final_score_100 = merged.final_score_100
    grade.ai_result = ai_result.model_dump()
    grade.raw_response = raw_json_str
    grade.static_analysis = static
    grade.needs_teacher_review = ai_result.needs_teacher_review or len(validation_errors) > 0
    if grade.needs_teacher_review:
        grade.review_reason = "; ".join(validation_errors) if validation_errors else ai_result.review_reason

    # 10. shadow 不改正式分，active 更新
    if grade.mode == "active" and not grade.needs_teacher_review:
        submission.score = merged.final_score_100
        submission.status = "graded"

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
