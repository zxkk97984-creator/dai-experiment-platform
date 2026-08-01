"""构建学生端可见的 AI 评分结果，只暴露安全字段。"""

from __future__ import annotations

from typing import Any


def _safe_items(ai: dict[str, Any], key: str) -> list[dict[str, Any]]:
    dimension = ai.get(key) if isinstance(ai, dict) else None
    if not isinstance(dimension, dict):
        return []
    items = dimension.get("items", [])
    if not isinstance(items, list):
        return []

    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append({
            "criterion_id": item.get("criterion_id"),
            "criterion": item.get("criterion"),
            "level": item.get("level"),
            "score": item.get("score"),
            "max_score": item.get("max_score"),
            "code_lines": item.get("code_lines", []),
            "evidence": item.get("evidence"),
            "deduction_reason": item.get("deduction_reason"),
        })
    return result


def build_student_grading_breakdown(cg: Any) -> dict[str, Any]:
    """从 CodeGrade 生成学生可见的 grading_breakdown。"""
    ai = cg.ai_result or {}
    feedback = ai.get("student_feedback", {}) or {}
    deterministic = cg.deterministic_details or {}
    groups = deterministic.get("groups", []) or []

    return {
        "functional_score": cg.functional_score,
        "algorithm_score": cg.algorithm_score,
        "robustness_score": cg.robustness_score,
        "quality_score": cg.quality_score,
        "raw_total": cg.raw_total,
        "score_cap": cg.score_cap,
        "final_score_100": cg.final_score_100,
        "scaled_score": cg.scaled_score,
        "strengths": feedback.get("strengths", []),
        "issues": feedback.get("issues", []),
        "suggestions": feedback.get("suggestions", []),
        "code_suggestions": feedback.get("code_suggestions", []),
        "algorithm_items": _safe_items(ai, "algorithm"),
        "quality_items": _safe_items(ai, "code_quality"),
        "test_groups": groups,
    }
