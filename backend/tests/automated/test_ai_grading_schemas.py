"""Task 3: AI 评分契约测试——配置校验、Rubric 文档、AI 输出、安全导出"""
import pytest
from pydantic import ValidationError


# ── 测试组配置 ──

def test_test_groups_must_total_60_and_10():
    """shadow/active 模式 F 组满分必须为 60，R 组满分必须为 10"""
    from app.schemas.ai_grading import AIQuestionConfigUpdate

    with pytest.raises(ValidationError):
        AIQuestionConfigUpdate(
            grading_mode="active",
            test_groups=[{"id": "F1", "name": "功能", "dimension": "F", "max_score": 50, "tests": "def test_x(): pass"}],
        )


def test_test_group_default_id_unique(db_session_factory):
    """重复 ID 的测试组应被拒绝"""
    from app.schemas.ai_grading import AIQuestionConfigUpdate

    with pytest.raises(ValidationError):
        AIQuestionConfigUpdate(
            grading_mode="active",
            test_groups=[
                {"id": "F1", "name": "基础", "dimension": "F", "max_score": 30, "tests": "def test_a(): pass"},
                {"id": "F1", "name": "核心", "dimension": "F", "max_score": 30, "tests": "def test_b(): pass"},
                {"id": "R1", "name": "边界", "dimension": "R", "max_score": 10, "tests": "def test_c(): pass"},
            ],
        )


def test_valid_test_groups_accepted():
    """合法的 F60+R10 配置应被接受"""
    from app.schemas.ai_grading import AIQuestionConfigUpdate

    config = AIQuestionConfigUpdate(
        grading_mode="active",
        test_groups=[
            {"id": "F1", "name": "基础功能", "dimension": "F", "max_score": 30, "tests": "def test_a(): pass"},
            {"id": "F2", "name": "核心功能", "dimension": "F", "max_score": 30, "tests": "def test_b(): pass"},
            {"id": "R1", "name": "边界测试", "dimension": "R", "max_score": 10, "tests": "def test_c(): pass"},
        ],
    )
    assert config.grading_mode == "active"
    assert len(config.test_groups) == 3


def test_legacy_skips_weight_validation():
    """legacy 模式不要求 F/R 比例校验"""
    from app.schemas.ai_grading import AIQuestionConfigUpdate

    config = AIQuestionConfigUpdate(
        grading_mode="legacy",
        test_groups=[],  # 可以不用测试组
    )
    assert config.grading_mode == "legacy"


def test_active_requires_test_groups():
    """active 模式必须有非空测试组"""
    from app.schemas.ai_grading import AIQuestionConfigUpdate

    with pytest.raises(ValidationError):
        AIQuestionConfigUpdate(
            grading_mode="active",
            test_groups=[],
        )


def test_invalid_dimension_rejected():
    """测试组只接受 F 或 R 维度"""
    from app.schemas.ai_grading import AIQuestionConfigUpdate

    with pytest.raises(ValidationError):
        AIQuestionConfigUpdate(
            grading_mode="active",
            test_groups=[
                {"id": "A1", "name": "算法", "dimension": "A", "max_score": 20, "tests": "def test_a(): pass"},
                {"id": "F1", "name": "功能", "dimension": "F", "max_score": 60, "tests": "def test_f(): pass"},
                {"id": "R1", "name": "边界", "dimension": "R", "max_score": 10, "tests": "def test_r(): pass"},
            ],
        )


def test_score_cap_rule_validation():
    """上限规则字段校验"""
    from app.schemas.ai_grading import ScoreCapRule

    # 合法规则
    rule = ScoreCapRule(
        id="CAP1",
        condition_code="off_topic",
        cap=30,
        description="文不对题，总分上限 30",
    )
    assert rule.cap == 30
    assert rule.condition_code == "off_topic"

    # cap 超出范围
    with pytest.raises(ValidationError):
        ScoreCapRule(
            id="CAP2",
            condition_code="off_topic",
            cap=150,
            description="无效上限",
        )


# ── AI 输出 ──

def test_ai_response_rejects_final_score():
    """AI 输出不得包含 final_score 字段"""
    from app.schemas.ai_grading import AIGradeResponse

    # 构建一个合法 payload 然后加入禁止字段
    payload = {
        "rubric_version": 1,
        "algorithm": {
            "dimension_score": 16,
            "dimension_max": 20,
            "items": [],
        },
        "code_quality": {
            "dimension_score": 8,
            "dimension_max": 10,
            "items": [],
        },
        "triggered_cap_rule_ids": [],
        "uncertainties": [],
        "needs_teacher_review": False,
        "review_reason": None,
        "student_feedback": {
            "strengths": ["功能正确"],
            "issues": [],
            "suggestions": [],
        },
        "final_score": 100,  # 禁止字段
    }
    with pytest.raises(ValidationError):
        AIGradeResponse.model_validate(payload)


def test_grade_item_level_validation():
    """评分项的等级只能是 complete/partial/missing"""
    from app.schemas.ai_grading import GradeItem

    item = GradeItem(
        criterion_id="A1",
        criterion="测试项",
        level="complete",
        score=4,
        max_score=4,
        code_lines=[1, 2],
        evidence="代码正确",
    )
    assert item.level == "complete"

    with pytest.raises(ValidationError):
        GradeItem(
            criterion_id="A1",
            criterion="测试项",
            level="invalid_level",  # 非法等级
            score=4,
            max_score=4,
            code_lines=[1],
            evidence="代码正确",
        )


def test_grade_item_negative_score_rejected():
    """评分项的分数不能为负"""
    from app.schemas.ai_grading import GradeItem

    with pytest.raises(ValidationError):
        GradeItem(
            criterion_id="A1",
            criterion="测试项",
            level="complete",
            score=-1,
            max_score=4,
            code_lines=[1],
            evidence="代码正确",
        )


def test_rubric_document_algorithm_total_20():
    """Rubric 算法项满分必须为 20"""
    from app.schemas.ai_grading import RubricDocument

    doc = RubricDocument(
        rubric_version=1,
        question_type="search_algorithm",
        learning_objective="掌握二分查找",
        explicit_requirements=["返回下标", "O(log n)"],
        teacher_constraints=[],
        accepted_strategies=["迭代二分", "递归二分"],
        algorithm_criteria=[
            {"id": "A1", "name": "搜索区间", "points": 10},
            {"id": "A2", "name": "缩小范围", "points": 10},
        ],
        quality_criteria=[
            {"id": "Q1", "name": "可读性", "points": 3},
            {"id": "Q2", "name": "代码结构", "points": 3},
            {"id": "Q3", "name": "重复与冗余", "points": 2},
            {"id": "Q4", "name": "接口规范", "points": 2},
        ],
        uncertain_items=[],
    )
    assert doc.rubric_version == 1

    # 算法分不为 20 时拒绝
    with pytest.raises(ValidationError):
        RubricDocument(
            rubric_version=1,
            question_type="search",
            learning_objective="测试",
            explicit_requirements=[],
            teacher_constraints=[],
            accepted_strategies=["任意"],
            algorithm_criteria=[
                {"id": "A1", "name": "搜索区间", "points": 5},
            ],
            quality_criteria=[
                {"id": "Q1", "name": "可读性", "points": 3},
                {"id": "Q2", "name": "结构", "points": 3},
                {"id": "Q3", "name": "冗余", "points": 2},
                {"id": "Q4", "name": "接口", "points": 2},
            ],
            uncertain_items=[],
        )
