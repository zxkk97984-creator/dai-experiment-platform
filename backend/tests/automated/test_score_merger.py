"""Task 7: 分数合并测试——固定公式、上限、考试折算"""
from app.services.score_merger import merge_scores


def test_merge_basic_100_scale():
    """F54 + A13 + R7 + Q5 = 79"""
    result = merge_scores(f=54, a=13, r=7, q=5, cap=None, exam_points=None)
    assert result.raw_total == 79
    assert result.final_score_100 == 79
    assert result.scaled_score == 79


def test_exam_score_is_scaled():
    """考试 25 分题：79/100 * 25 = 19.75"""
    result = merge_scores(f=54, a=13, r=7, q=5, cap=None, exam_points=25)
    assert result.raw_total == 79
    assert result.final_score_100 == 79
    assert result.scaled_score == 19.75


def test_cap_limits_score():
    """上限 80：raw=87 → final=80"""
    result = merge_scores(f=60, a=18, r=9, q=8, cap=80, exam_points=None)
    assert result.raw_total == 95
    assert result.final_score_100 == 80
    assert result.scaled_score == 80


def test_cap_not_exceeded():
    """raw=79，上限=80，不触发上限"""
    result = merge_scores(f=54, a=13, r=7, q=5, cap=80, exam_points=None)
    assert result.raw_total == 79
    assert result.final_score_100 == 79


def test_rounded_scores():
    """分数保留 4 位小数"""
    result = merge_scores(f=54.1234, a=13.5678, r=7.9999, q=5.0001, cap=None, exam_points=None)
    assert result.raw_total == round(54.1234 + 13.5678 + 7.9999 + 5.0001, 4)
