"""Task 7: AI 输出校验测试——A/Q 业务规则、越界行号、重复扣分"""
import pytest


def test_validates_rubric_version_mismatch():
    """Rubric 版本不匹配时拒绝"""
    from app.services.ai_score_validation import validate_ai_output

    rubric = {
        "rubric_version": 2,
        "algorithm_criteria": [
            {"id": "A1", "name": "搜索区间", "points": 10},
            {"id": "A2", "name": "缩小范围", "points": 10},
        ],
    }

    ai_result = {
        "rubric_version": 1,  # 版本不匹配
        "algorithm": {
            "dimension_score": 20,
            "dimension_max": 20,
            "items": [
                {"criterion_id": "A1", "criterion": "搜索区间", "level": "complete", "score": 10, "max_score": 10, "code_lines": [1], "evidence": "ok"},
                {"criterion_id": "A2", "criterion": "缩小范围", "level": "complete", "score": 10, "max_score": 10, "code_lines": [2], "evidence": "ok"},
            ],
        },
        "code_quality": {
            "dimension_score": 10,
            "dimension_max": 10,
            "items": [],
        },
    }

    errors = validate_ai_output(rubric, ai_result, code_lines=[1, 2])
    assert len(errors) > 0
    assert any("不匹配" in e for e in errors)


def test_rejects_unknown_criterion():
    """Rubric 中不存在的 criterion_id 被拒绝"""
    from app.services.ai_score_validation import validate_ai_output

    rubric = {
        "rubric_version": 1,
        "algorithm_criteria": [
            {"id": "A1", "name": "搜索区间", "points": 10},
        ],
    }

    ai_result = {
        "rubric_version": 1,
        "algorithm": {
            "dimension_score": 10,
            "dimension_max": 20,
            "items": [
                {"criterion_id": "A99", "criterion": "不存在", "level": "complete", "score": 10, "max_score": 10, "code_lines": [1], "evidence": "ok"},
            ],
        },
        "code_quality": {
            "dimension_score": 10,
            "dimension_max": 10,
            "items": [],
        },
    }

    errors = validate_ai_output(rubric, ai_result, code_lines=[1])
    assert len(errors) > 0
    assert any("A99" in e for e in errors)


def test_rejects_out_of_range_line():
    """行号超出代码范围被拒绝"""
    from app.services.ai_score_validation import validate_ai_output

    rubric = {
        "rubric_version": 1,
        "algorithm_criteria": [
            {"id": "A1", "name": "搜索区间", "points": 20},
        ],
    }

    ai_result = {
        "rubric_version": 1,
        "algorithm": {
            "dimension_score": 20,
            "dimension_max": 20,
            "items": [
                {"criterion_id": "A1", "criterion": "搜索区间", "level": "complete", "score": 20, "max_score": 20, "code_lines": [999], "evidence": "ok"},
            ],
        },
        "code_quality": {
            "dimension_score": 10,
            "dimension_max": 10,
            "items": [],
        },
    }

    errors = validate_ai_output(rubric, ai_result, code_lines=[1, 2, 3])
    assert len(errors) > 0
    assert any("999" in e or "行号" in e for e in errors)


def test_duplicate_reason_across_aq_triggers_review():
    """A 和 Q 中相同 reason_code 且代码行重叠触发 teacher_review"""
    from app.services.ai_score_validation import detect_cross_dimension_duplicates

    a_items = [
        {"criterion_id": "A1", "reason_code": "wrong_boundary", "code_lines": [5, 6, 7]},
    ]
    q_items = [
        {"criterion_id": "Q2", "reason_code": "wrong_boundary", "code_lines": [6, 7]},
    ]

    duplicates = detect_cross_dimension_duplicates(a_items, q_items)
    assert len(duplicates) > 0
