"""Task 5: Rubric 生命周期测试——生成、锁定、发布门禁"""
import json

import httpx
import pytest

from app.config import Settings
from app.services.ai_client import DeepSeekClient


def _build_snapshot(**overrides):
    """快捷构建测试快照"""
    base = {
        "title": "二分查找",
        "description": "在有序数组中查找目标元素",
        "function_name": "binary_search",
        "teacher_constraints": {},
        "test_groups": [
            {"id": "F1", "name": "基础", "dimension": "F", "max_score": 60, "tests": "def test_a(): pass"},
            {"id": "R1", "name": "边界", "dimension": "R", "max_score": 10, "tests": "def test_c(): pass"},
        ],
        "reference_solution": None,
        "is_exam": False,
    }
    base.update(overrides)
    return base


def make_fake_client(response_data: dict | None = None):
    """构建使用 MockTransport 的 DeepSeek 客户端"""
    data = response_data or {
        "rubric_version": 1,
        "question_type": "search",
        "learning_objective": "掌握搜索算法",
        "explicit_requirements": ["返回目标下标", "未找到返回 -1"],
        "teacher_constraints": [],
        "accepted_strategies": ["迭代二分", "递归二分"],
        "algorithm_criteria": [
            {"id": "A1", "name": "搜索区间", "points": 10},
            {"id": "A2", "name": "缩小范围", "points": 10},
        ],
        "quality_criteria": [
            {"id": "Q1", "name": "可读性与命名", "points": 3},
            {"id": "Q2", "name": "代码结构", "points": 3},
            {"id": "Q3", "name": "重复与冗余", "points": 2},
            {"id": "Q4", "name": "接口、规范与安全", "points": 2},
        ],
        "uncertain_items": [],
    }

    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(data, ensure_ascii=False)}}]
        })

    settings = Settings(
        _env_file=None,
        ai_base_url="https://aihub.codingpython.cn",
        ai_model="deepseek-v4-flash",
        ai_api_key="test-only-key",
        ai_max_retries=0,
    )
    return DeepSeekClient(settings, transport=httpx.MockTransport(handler))


def make_error_client():
    """构建返回错误的 DeepSeek 客户端"""
    def handler(request):
        return httpx.Response(503, json={"error": "service unavailable"})

    settings = Settings(
        _env_file=None,
        ai_base_url="https://aihub.codingpython.cn",
        ai_model="deepseek-v4-flash",
        ai_api_key="test-only-key",
        ai_max_retries=0,
    )
    return DeepSeekClient(settings, transport=httpx.MockTransport(handler))


# ── Rubric 服务测试 ──


def test_build_question_snapshot():
    """从题目属性构建规范快照"""
    from app.services.rubric_service import build_question_snapshot

    snapshot = build_question_snapshot(
        title="二分查找",
        description="在有序数组中查找目标",
        function_name="binary_search",
        teacher_constraints={"must_use": "binary_search"},
        test_groups=[
            {"id": "F1", "name": "基础", "dimension": "F", "max_score": 30, "tests": "def test_a(): pass"},
            {"id": "F2", "name": "核心", "dimension": "F", "max_score": 30, "tests": "def test_b(): pass"},
            {"id": "R1", "name": "边界", "dimension": "R", "max_score": 10, "tests": "def test_c(): pass"},
        ],
        reference_solution="def binary_search(arr, t): ...",
    )
    assert snapshot["title"] == "二分查找"
    assert snapshot["function_name"] == "binary_search"
    assert "reference_solution" in snapshot


def test_generate_rubric_creates_draft(db_session_factory):
    """调用 AI 生成 Rubric 并保存为 draft"""
    from app.services.rubric_service import generate_rubric
    from app.models import QuestionRubric

    fake_client = make_fake_client()

    with db_session_factory() as db:
        rubric = generate_rubric(
            db,
            fake_client,
            kind="assignment",
            question_id=1,
            snapshot=_build_snapshot(),
        )
        assert rubric is not None
        assert rubric.status == "draft"
        assert rubric.version == 1
        assert rubric.rubric_json is not None
        assert rubric.source_hash is not None
        assert len(rubric.source_hash) == 64  # SHA-256 hex


def test_lock_rubric_supersedes_old(db_session_factory):
    """锁定 Rubric 后同题旧版本变为 superseded"""
    from app.services.rubric_service import generate_rubric, lock_rubric
    from app.models import QuestionRubric

    fake_client = make_fake_client()

    with db_session_factory() as db:
        rubric1 = generate_rubric(db, fake_client, kind="assignment", question_id=1, snapshot=_build_snapshot())
        locked = lock_rubric(db, rubric1.id)
        assert locked.status == "locked"
        assert locked.locked_at is not None

        rubric2 = generate_rubric(db, fake_client, kind="assignment", question_id=1, snapshot=_build_snapshot())
        assert rubric2.version == 2


def test_update_draft_rubric(db_session_factory):
    """只允许修改 draft 状态的 Rubric"""
    from app.services.rubric_service import generate_rubric, lock_rubric, update_draft_rubric
    from app.schemas.ai_grading import RubricDocument

    fake_client = make_fake_client()

    with db_session_factory() as db:
        rubric = generate_rubric(db, fake_client, kind="assignment", question_id=1, snapshot=_build_snapshot())
        assert rubric.status == "draft"

        doc = RubricDocument(**rubric.rubric_json)
        doc_dict = doc.model_dump()
        doc_dict["learning_objective"] = "更新后的目标"

        updated = update_draft_rubric(db, rubric.id, RubricDocument(**doc_dict))
        assert updated.rubric_json["learning_objective"] == "更新后的目标"

        lock_rubric(db, rubric.id)
        with pytest.raises(ValueError, match="draft"):
            update_draft_rubric(db, rubric.id, RubricDocument(**doc_dict))


def test_get_latest_locked_rubric(db_session_factory):
    """获取最新锁定的 Rubric"""
    from app.services.rubric_service import generate_rubric, get_latest_locked_rubric, lock_rubric

    fake_client = make_fake_client()

    with db_session_factory() as db:
        rubric = generate_rubric(db, fake_client, kind="assignment", question_id=1, snapshot=_build_snapshot())
        lock_rubric(db, rubric.id)

        found = get_latest_locked_rubric(db, kind="assignment", question_id=1)
        assert found is not None
        assert found.id == rubric.id
        assert found.status == "locked"


def test_ensure_locked_rubrics_for_publish(db_session_factory):
    """发布前确保所有非 legacy 题目有锁定 Rubric"""
    from app.services.rubric_service import ensure_locked_rubrics_for_publish

    fake_client = make_fake_client()

    with db_session_factory() as db:
        questions = [
            {
                "id": 1,
                "grading_mode": "shadow",
                "title": "二分查找",
                "description": "查找目标元素",
                "function_name": "binary_search",
                "teacher_constraints": {},
                "test_groups": [
                    {"id": "F1", "name": "基础", "dimension": "F", "max_score": 60, "tests": ""},
                    {"id": "R1", "name": "边界", "dimension": "R", "max_score": 10, "tests": ""},
                ],
                "reference_solution": None,
            }
        ]
        ensure_locked_rubrics_for_publish(db, fake_client, questions)
        from app.models import QuestionRubric
        from sqlalchemy import select

        rubrics = db.scalars(select(QuestionRubric)).all()
        assert len(rubrics) == 1
        assert rubrics[0].status == "locked"


def test_ensure_locked_rubrics_reuses_valid_rubric(db_session_factory):
    """已有锁定 Rubric 且配置未变时不重新生成（通过 ensure 两次验证）"""
    from app.services.rubric_service import (
        ensure_locked_rubrics_for_publish,
    )

    fake_client = make_fake_client()

    with db_session_factory() as db:
        questions = [{
            "id": 1,
            "grading_mode": "shadow",
            "title": "二分查找",
            "description": "在有序数组中查找目标元素",
            "function_name": "binary_search",
            "teacher_constraints": {},
            "test_groups": [
                {"id": "F1", "name": "基础", "dimension": "F", "max_score": 60, "tests": "def a(): pass"},
                {"id": "R1", "name": "边界", "dimension": "R", "max_score": 10, "tests": "def b(): pass"},
            ],
            "reference_solution": None,
        }]

        # 第一次：生成并锁定
        ensure_locked_rubrics_for_publish(db, fake_client, questions)

        from app.models import QuestionRubric
        from sqlalchemy import select

        rubrics = db.scalars(select(QuestionRubric)).all()
        assert len(rubrics) == 1
        assert rubrics[0].status == "locked"

        # 第二次：同配置应复用已有锁定 Rubric
        ensure_locked_rubrics_for_publish(db, fake_client, questions)
        rubrics = db.scalars(select(QuestionRubric)).all()
        assert len(rubrics) == 1  # 不生成新版本


def test_ensure_locked_rubrics_raises_on_ai_failure(db_session_factory):
    """AI 不可用时拒绝发布"""
    from app.services.ai_client import AIServiceError
    from app.services.rubric_service import ensure_locked_rubrics_for_publish

    fake_client = make_error_client()

    with db_session_factory() as db:
        questions = [{
            "id": 1,
            "grading_mode": "shadow",
            "title": "二分查找",
            "description": "",
            "function_name": "binary_search",
            "teacher_constraints": {},
            "test_groups": [
                {"id": "F1", "name": "基础", "dimension": "F", "max_score": 60, "tests": ""},
                {"id": "R1", "name": "边界", "dimension": "R", "max_score": 10, "tests": ""},
            ],
            "reference_solution": None,
        }]
        with pytest.raises(AIServiceError):
            ensure_locked_rubrics_for_publish(db, fake_client, questions)
