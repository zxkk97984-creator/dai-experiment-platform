"""Task 10: 教师复核测试——权限、覆盖审计、重试、统一重评"""
import pytest

from app.schemas.ai_grading import GradeOverrideCreate


def test_override_requires_reason():
    """覆盖操作必须提供理由"""
    with pytest.raises(Exception):  # ValidationError
        GradeOverrideCreate(
            algorithm_score=15,
            reason="ab",  # 太短
        )


def test_override_at_least_one_field():
    """覆盖至少指定一项"""
    with pytest.raises(Exception):
        GradeOverrideCreate(
            reason="至少需要指定一项分数",
        )


def test_override_valid_request():
    """合法的覆盖请求"""
    override = GradeOverrideCreate(
        algorithm_score=18,
        reason="学生实际完成了正确算法，AI 误判",
    )
    assert override.algorithm_score == 18
    assert override.quality_score is None
    assert override.final_score_100 is None


def test_override_final_score_solo():
    """仅覆盖最终分"""
    override = GradeOverrideCreate(
        final_score_100=85,
        reason="综合评估后调整总分",
    )
    assert override.final_score_100 == 85


def test_override_score_bounds():
    """覆盖分数必须在合法范围内"""
    with pytest.raises(Exception):
        GradeOverrideCreate(
            algorithm_score=25,  # A 上限 20
            reason="超出算法分上限",
        )

    with pytest.raises(Exception):
        GradeOverrideCreate(
            quality_score=15,  # Q 上限 10
            reason="超出质量分上限",
        )

    with pytest.raises(Exception):
        GradeOverrideCreate(
            final_score_100=150,  # 超出 100
            reason="超出总分上限",
        )
