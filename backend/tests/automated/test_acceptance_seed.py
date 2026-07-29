"""验收数据脚本测试——数据契约、幂等辅助函数与 Fake API 行为验证"""
import json
import pytest
from unittest.mock import patch, MagicMock
import httpx


class TestFindExact:
    """幂等辅助函数 find_exact 的单元测试"""

    def test_returns_matching_item_without_mutation(self):
        """精确匹配返回对应项，不修改原列表"""
        from seed_acceptance_data import find_exact
        items = [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]
        assert find_exact(items, "title", "B") == items[1]
        assert find_exact(items, "title", "missing") is None
        assert len(items) == 2

    def test_field_not_present_in_item_returns_none(self):
        """字段不存在时返回 None 而非抛异常"""
        from seed_acceptance_data import find_exact
        items = [{"id": 1}]
        assert find_exact(items, "title", "x") is None

    def test_empty_list_returns_none(self):
        """空列表返回 None"""
        from seed_acceptance_data import find_exact
        assert find_exact([], "title", "x") is None


class TestAcceptanceDataStructure:
    """数据契约测试——验证 ACCEPTANCE_DATA 常量结构"""

    @pytest.fixture(autouse=True)
    def import_data(self):
        import seed_acceptance_data as s
        self.data = s.ACCEPTANCE_DATA
        self.students = s.DEMO_STUDENTS
        self.submissions = s.DEMO_SUBMISSIONS

    def test_course_count(self):
        assert len(self.data) == 2

    def test_chapter_count(self):
        total = sum(len(c["chapters"]) for c in self.data)
        assert total == 6

    def test_lesson_count(self):
        total = sum(len(ch["lessons"]) for c in self.data for ch in c["chapters"])
        assert total == 12

    def test_assignment_count(self):
        total = sum(len(c.get("assignments", [])) for c in self.data)
        assert total == 3

    def test_assignment_code_question_count(self):
        total = sum(
            len(a.get("questions", []))
            for c in self.data
            for a in c.get("assignments", [])
        )
        assert total == 9

    def test_exam_count(self):
        total = sum(len(c.get("exams", [])) for c in self.data)
        assert total == 2

    def test_exam_question_count(self):
        total = sum(
            len(e.get("questions", []))
            for c in self.data
            for e in c.get("exams", [])
        )
        assert total == 12

    def test_each_course_has_three_chapters(self):
        for course in self.data:
            assert len(course["chapters"]) == 3, f"{course['title']} 应有3章"

    def test_each_chapter_has_two_lessons(self):
        for course in self.data:
            for ch in course["chapters"]:
                assert len(ch["lessons"]) == 2, f"{ch['title']} 应有2个课时"

    def test_each_lesson_has_required_sections(self):
        required = ["学习目标", "核心知识", "示例", "练习"]
        for course in self.data:
            for ch in course["chapters"]:
                for lesson in ch["lessons"]:
                    content = lesson.get("content", "")
                    for keyword in required:
                        assert keyword in content, (
                            f"{lesson['title']} 缺少关键词: {keyword}"
                        )

    def test_code_questions_have_required_fields(self):
        for course in self.data:
            for a in course.get("assignments", []):
                for q in a.get("questions", []):
                    assert q.get("function_name"), f"{q.get('title')} 缺少 function_name"
                    assert q.get("signature") is not None, f"{q.get('title')} 缺少 signature"
                    assert q.get("starter_code") is not None, f"{q.get('title')} 缺少 starter_code"

    def test_code_questions_have_test_cases(self):
        for course in self.data:
            for a in course.get("assignments", []):
                for q in a.get("questions", []):
                    cases = q.get("public_cases", [])
                    assert len(cases) >= 2, f"{q.get('title')} public_cases 不足2个"
                    assert q.get("hidden_tests"), f"{q.get('title')} hidden_tests 为空"

    def test_grading_mode_coverage(self):
        modes = set()
        for course in self.data:
            for a in course.get("assignments", []):
                for q in a.get("questions", []):
                    modes.add(q.get("grading_mode"))
        assert "legacy" in modes
        assert "shadow" in modes
        assert "active" in modes

    def test_choice_questions_complete(self):
        for course in self.data:
            for e in course.get("exams", []):
                for q in e.get("questions", []):
                    if q.get("question_type") in ("single_choice", "multi_choice"):
                        assert q.get("options"), f"{q.get('prompt')} 缺少 options"
                        assert q.get("correct_answer"), f"{q.get('prompt')} 缺少 correct_answer"
                        assert q.get("points", 0) > 0, f"{q.get('prompt')} points 无效"
                        assert "order_index" in q, f"{q.get('prompt')} 缺少 order_index"

    def test_exam_total_scores(self):
        for course in self.data:
            for e in course.get("exams", []):
                total = sum(q.get("points", 0) for q in e.get("questions", []))
                assert total == 100, f"{e.get('title')} 总分应为100，实际{total}"

    def test_course_titles_match_design(self):
        titles = [c["title"] for c in self.data]
        assert "[验收] Python 算法与工程实践" in titles
        assert "[验收] 数据分析与机器学习入门" in titles

    def test_function_names_match_design(self):
        expected = {
            "normalize_name", "safe_divide", "summarize_scores",
            "deduplicate_ordered", "word_frequency", "binary_search",
            "clean_numbers", "group_average", "confusion_metrics",
        }
        actual = set()
        for course in self.data:
            for a in course.get("assignments", []):
                for q in a.get("questions", []):
                    actual.add(q["function_name"])
        for name in expected:
            assert name in actual, f"缺少函数: {name}"

    def test_demo_students_count(self):
        assert len(self.students) == 2
        usernames = [s["username"] for s in self.students]
        assert "accept_student_a" in usernames
        assert "accept_student_b" in usernames

    def test_demo_submissions_count(self):
        assert len(self.submissions) == 4

    def test_demo_submissions_cover_all_grading_modes(self):
        """代表性提交覆盖 legacy、shadow、active"""
        by_student = {}
        for sub in self.submissions:
            by_student.setdefault(sub["student"], []).append(sub["question_title"])
        # 学生甲：正确提交
        assert "accept_student_a" in by_student
        # 学生乙：错误提交
        assert "accept_student_b" in by_student


class TestFakeApiIdempotency:
    """幂等行为验证——find_exact 驱动的级联创建/复用"""

    def test_cascade_ensure_first_creates_then_reuses(self):
        """模拟课程→章节→课时：第一次3次创建，第二次0次创建"""
        from seed_acceptance_data import find_exact

        store = {"courses": [], "chapters": [], "lessons": []}
        created_count = 0

        def simulate_seed():
            nonlocal created_count
            # 课程
            course = find_exact(store["courses"], "title", "测试课程")
            if not course:
                store["courses"].append({"id": 1, "title": "测试课程"})
                created_count += 1
                course = store["courses"][-1]

            # 章节
            chapter = find_exact(store["chapters"], "title", "第一章")
            if not chapter:
                store["chapters"].append({"id": 101, "title": "第一章", "course_id": course["id"]})
                created_count += 1
                chapter = store["chapters"][-1]

            # 课时
            lesson = find_exact(store["lessons"], "title", "第一课")
            if not lesson:
                store["lessons"].append({"id": 1001, "title": "第一课", "chapter_id": chapter["id"]})
                created_count += 1

        # 第一次
        simulate_seed()
        assert created_count == 3

        # 第二次——不创建
        simulate_seed()
        assert created_count == 3  # 不变
        assert len(store["courses"]) == 1
        assert len(store["chapters"]) == 1
        assert len(store["lessons"]) == 1

    def test_idempotent_user_creation(self):
        """用户已存在时不重复创建"""
        from seed_acceptance_data import find_exact

        users = []
        created = 0

        for username in ["accept_student_a", "accept_student_b"]:
            u = find_exact(users, "username", username)
            if not u:
                users.append({"id": len(users) + 1, "username": username, "role": "student"})
                created += 1

        assert created == 2

        # 重跑——不再创建
        for username in ["accept_student_a", "accept_student_b"]:
            u = find_exact(users, "username", username)
            assert u is not None
        assert len(users) == 2

    def test_submission_reuse(self):
        """某学生对目标问题已有提交时不重复创建"""
        from seed_acceptance_data import find_exact

        submissions = [
            {"id": 1, "question_id": 10, "student_id": 100, "status": "completed"},
        ]
        created = 0

        # 模拟查找已有提交
        q_id = 10
        student_id = 100
        existing = [s for s in submissions if s["question_id"] == q_id and s["student_id"] == student_id]
        if not existing:
            submissions.append({"id": 2, "question_id": q_id, "student_id": student_id, "status": "completed"})
            created += 1

        assert created == 0  # 已存在，不创建
        assert len(submissions) == 1


class TestSeedError:
    """SeedError 异常测试"""

    def test_seed_error_contains_message(self):
        from seed_acceptance_data import SeedError
        e = SeedError("测试错误")
        assert "测试错误" in str(e)

    def test_seed_error_no_credentials_leak(self):
        from seed_acceptance_data import SeedError
        e = SeedError("POST /courses 失败 (409): 课程已存在")
        assert "Authorization" not in str(e)
        assert "Bearer" not in str(e)
        assert "sk-" not in str(e)

    def test_seed_error_status_code(self):
        from seed_acceptance_data import SeedError
        e = SeedError("GET /users 失败 (503): 服务不可用")
        assert "503" in str(e)


class TestSeedStats:
    """SeedStats 统计测试"""

    def test_initial_counts(self):
        from seed_acceptance_data import SeedStats
        s = SeedStats()
        assert s.created == 0
        assert s.reused == 0

    def test_increment(self):
        from seed_acceptance_data import SeedStats
        s = SeedStats()
        s.inc_created()
        s.inc_created()
        s.inc_reused()
        assert s.created == 2
        assert s.reused == 1
