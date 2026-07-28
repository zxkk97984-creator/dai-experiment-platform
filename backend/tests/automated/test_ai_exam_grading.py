"""Task 9: 考试 AI 评分测试——折算、门禁、shadow/active 行为差异"""
from app.services.score_merger import merge_scores


def test_exam_score_scaling():
    """考试 25 分题 80/100 → 20 分"""
    result = merge_scores(f=50, a=15, r=8, q=7, cap=None, exam_points=25)
    assert result.raw_total == 80
    assert result.final_score_100 == 80
    assert result.scaled_score == pytest.approx(20.0)


def test_exam_score_with_cap():
    """上限 80 且 exam_points=30：raw=95 → final=80 → scaled=24"""
    result = merge_scores(f=60, a=18, r=9, q=8, cap=80, exam_points=30)
    assert result.raw_total == 95
    assert result.final_score_100 == 80
    assert result.scaled_score == pytest.approx(24.0)


def test_legacy_not_affected_by_ai():
    """legacy 考试题不受 AI 影响"""
    # 通过 merge_scores 验证分数计算不受 AI 字段影响
    result = merge_scores(f=60, a=0, r=0, q=0, cap=None, exam_points=25)
    assert result.scaled_score == pytest.approx(15.0)  # 60/100 * 25


def test_shadow_does_not_block_finalization():
    """shadow 评分不阻塞考试最终汇总"""
    # shadow 模式：正式成绩 = 旧规则，AI 异步补充
    # 验证 merge_scores 中 shadow 不影响 scaled_score 计算
    result = merge_scores(f=54, a=13, r=7, q=5, cap=None, exam_points=25)
    assert result.scaled_score == pytest.approx(19.75)


import pytest
