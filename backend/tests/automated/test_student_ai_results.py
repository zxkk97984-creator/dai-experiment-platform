"""学生端 AI 评分结果安全字段测试。"""

from types import SimpleNamespace

from app.services.student_ai_results import build_student_grading_breakdown


def test_student_breakdown_exposes_safe_fields():
    cg = SimpleNamespace(
        ai_result={
            "algorithm": {
                "items": [
                    {
                        "criterion_id": "A1",
                        "criterion": "维护搜索区间",
                        "level": "partial",
                        "score": 3,
                        "max_score": 4,
                        "code_lines": [2],
                        "evidence": "边界未覆盖",
                        "deduction_reason": "缺少空输入判断",
                    }
                ]
            },
            "code_quality": {"items": []},
            "student_feedback": {
                "strengths": ["功能正确"],
                "issues": ["边界缺失"],
                "suggestions": ["补充空输入"],
                "code_suggestions": [
                    {"title": "补全空输入", "diff": "--- a/solution.py\n+++ b/solution.py\n+    return []\n"}
                ],
            },
        },
        deterministic_details={
            "groups": [
                {
                    "id": "F1",
                    "name": "功能正确性",
                    "max_score": 60,
                    "score": 54,
                    "counts": {"passed": 3, "failed": 1, "errors": 0, "skipped": 0},
                }
            ]
        },
        functional_score=54,
        algorithm_score=13,
        robustness_score=7,
        quality_score=5,
        raw_total=79,
        score_cap=None,
        final_score_100=79,
        scaled_score=None,
    )

    result = build_student_grading_breakdown(cg)

    assert result["final_score_100"] == 79
    assert result["algorithm_items"][0]["criterion"] == "维护搜索区间"
    assert result["algorithm_items"][0]["deduction_reason"] == "缺少空输入判断"
    assert result["test_groups"][0]["counts"]["failed"] == 1
    assert result["code_suggestions"][0]["diff"].startswith("--- ")
    assert "strengths" in result
    assert "issues" in result
    assert "suggestions" in result
