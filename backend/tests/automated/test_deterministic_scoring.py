"""Task 6: 确定性 F/R 评分测试——测试组计分、pytest 结果解析、系统错误处理"""
import pytest

from app.schemas.ai_grading import TestGroup


def test_group_score_uses_pass_ratio():
    """3/4 通过的 20 分组得到 15 分"""
    from app.services.deterministic_scoring import calculate_group_score

    score = calculate_group_score(20, {"passed": 3, "failed": 1, "errors": 0, "skipped": 0})
    assert score == pytest.approx(15.0)


def test_all_passed_full_score():
    """全部通过得到满分"""
    from app.services.deterministic_scoring import calculate_group_score

    score = calculate_group_score(30, {"passed": 5, "failed": 0, "errors": 0, "skipped": 2})
    assert score == pytest.approx(30.0)


def test_all_failed_zero_score():
    """全部失败得零分"""
    from app.services.deterministic_scoring import calculate_group_score

    score = calculate_group_score(10, {"passed": 0, "failed": 3, "errors": 0, "skipped": 0})
    assert score == pytest.approx(0.0)


def test_no_countable_tests_system_error():
    """没有可计数用例时抛出系统错误"""
    from app.services.deterministic_scoring import DeterministicSystemError, calculate_group_score

    with pytest.raises(DeterministicSystemError):
        calculate_group_score(10, {"passed": 0, "failed": 0, "errors": 0, "skipped": 2})


def test_errors_count_as_denominator():
    """errors 计入分母（不算通过）"""
    from app.services.deterministic_scoring import calculate_group_score

    score = calculate_group_score(20, {"passed": 1, "failed": 1, "errors": 1, "skipped": 0})
    assert score == pytest.approx(20 * 1 / 3, rel=1e-3)


def test_parse_result_json():
    """解析 pytest 插件的 DAI_RESULT_JSON= 输出"""
    from app.services.deterministic_scoring import parse_result_json

    output = "collected 10 items\nDAI_RESULT_JSON={\"passed\":3,\"failed\":1,\"errors\":0,\"skipped\":0}\n"
    result = parse_result_json(output)
    assert result == {"passed": 3, "failed": 1, "errors": 0, "skipped": 0}


def test_parse_result_json_invalid_output():
    """无效输出返回 None"""
    from app.services.deterministic_scoring import parse_result_json

    assert parse_result_json("") is None
    assert parse_result_json("no json here") is None
    assert parse_result_json("DAI_RESULT_JSON=not valid json") is None


def test_deterministic_grade_sums():
    """确定性评分汇总 F 和 R"""
    from app.services.deterministic_scoring import calculate_deterministic_grade

    groups = [
        TestGroup(id="F1", name="基础", dimension="F", max_score=30, tests="def test_a(): pass"),
        TestGroup(id="F2", name="核心", dimension="F", max_score=30, tests="def test_b(): pass"),
        TestGroup(id="R1", name="边界", dimension="R", max_score=10, tests="def test_c(): pass"),
    ]
    results = {
        "F1": {"passed": 2, "failed": 1, "errors": 0, "skipped": 0},
        "F2": {"passed": 3, "failed": 0, "errors": 0, "skipped": 0},
        "R1": {"passed": 3, "failed": 1, "errors": 0, "skipped": 1},
    }

    grade = calculate_deterministic_grade(groups, results)
    # F1: 30 * 2/3 = 20; F2: 30 * 3/3 = 30; F = 50
    # R1: 10 * 3/4 = 7.5; R = 7.5
    assert grade.functional_score == pytest.approx(50.0)
    assert grade.robustness_score == pytest.approx(7.5)
    assert len(grade.system_errors) == 0
