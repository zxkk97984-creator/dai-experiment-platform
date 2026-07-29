"""Task 4: AI 提示词测试——Rubric 生成与代码评分提示词"""
from app.services.ai_prompts import build_grading_messages, build_rubric_messages


def test_rubric_messages_contain_required_sections():
    """Rubric 生成提示词包含必要约束"""
    snapshot = {
        "title": "二分查找",
        "description": "在有序数组中查找目标元素",
        "function_name": "binary_search",
        "is_exam": False,
        "teacher_constraints": [],
        "test_groups": [
            {"id": "F1", "name": "基础功能", "dimension": "F", "max_score": 30},
            {"id": "F2", "name": "核心功能", "dimension": "F", "max_score": 30},
            {"id": "R1", "name": "边界测试", "dimension": "R", "max_score": 10},
        ],
    }
    messages = build_rubric_messages(snapshot)
    # 应有 system + user
    assert len(messages) >= 2
    system_msg = messages[0]["content"]
    # 关键约束
    assert "参考代码" in system_msg or "唯一" in system_msg
    assert "20" in system_msg or "总分" in system_msg
    assert "uncertain_items" in system_msg or "不确定" in system_msg
    # 用户消息包含题目信息
    user_msg = messages[-1]["content"]
    assert "二分查找" in user_msg


def test_grading_messages_contain_untrusted_tags():
    """评分提示词使用不可信数据标记"""
    code = "def binary_search(arr, target):\n    pass\n"
    messages = build_grading_messages(
        rubric={"rubric_version": 1, "algorithm_criteria": []},
        question={"title": "测试题", "description": "测试"},
        code=code,
        deterministic={"functional_score": 54, "robustness_score": 7},
        static_analysis={"parseable": True},
    )
    # 应有 system + user
    assert len(messages) >= 2
    system_msg = messages[0]["content"]
    # 关键约束
    assert "F" in system_msg or "R" in system_msg or "最终总分" in system_msg or "总分" in system_msg
    assert "参考代码" in system_msg or "唯一" in system_msg
    user_msg = messages[-1]["content"]
    assert "untrusted_student_code" in user_msg or "不可信" in user_msg


def test_grading_messages_include_line_numbers():
    """评分提示词学生代码带行号"""
    code = "def add(a, b):\n    return a + b\n"
    messages = build_grading_messages(
        rubric={"rubric_version": 1, "algorithm_criteria": []},
        question={"title": "测试"},
        code=code,
        deterministic={"functional_score": 60, "robustness_score": 10},
        static_analysis={"parseable": True},
    )
    user_msg = messages[-1]["content"]
    # 应该包含带行号的代码
    assert "1" in user_msg  # 行号
    assert "def add" in user_msg


def test_grading_messages_do_not_leak_rubric_raw_response():
    """提示词不包含 AI 原始响应"""
    messages = build_grading_messages(
        rubric={
            "rubric_version": 1,
            "algorithm_criteria": [
                {"id": "A1", "name": "搜索区间", "points": 10},
                {"id": "A2", "name": "缩小范围", "points": 10},
            ],
        },
        question={"title": "测试"},
        code="def solve(): pass",
        deterministic={"functional_score": 60, "robustness_score": 10},
        static_analysis={"parseable": True},
    )
    user_msg = messages[-1]["content"]
    # 不应包含 raw_response（如果有的话）
    assert "raw_response" not in user_msg.lower()


def test_grading_messages_pin_database_locked_rubric_version():
    """评分请求必须使用数据库锁定版本，而不是 rubric_json 中陈旧的版本 1。"""
    messages = build_grading_messages(
        rubric={
            "rubric_version": 1,
            "algorithm_criteria": [
                {"id": "A1", "name": "核心步骤", "points": 20},
            ],
            "quality_criteria": [],
        },
        rubric_version=3,
        question={"title": "多版本 Rubric 题目"},
        code="def solve():\n    return 1",
        deterministic={"functional_score": 60, "robustness_score": 10},
        static_analysis={"parseable": True},
    )

    user_msg = messages[-1]["content"]
    assert '"rubric_version": 3' in user_msg
    assert "输出中的 rubric_version 必须严格等于 3" in user_msg
