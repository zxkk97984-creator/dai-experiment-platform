"""发布 3 道 active 模式练习题，用于实际体验 AI 评分。"""

import os
import textwrap

import requests


BASE_URL = os.environ.get("DAI_DEMO_BASE_URL", "http://localhost:8000/api/v1")
TEACHER_USERNAME = os.environ.get("DAI_DEMO_TEACHER_USERNAME", "teacher_john")
TEACHER_PASSWORD = os.environ.get("DAI_DEMO_TEACHER_PASSWORD", "Test1234!")
COURSE_TITLE = "Python编程与算法实战"
ASSIGNMENT_TITLE = "AI 评分体验作业"


def clean_tests(code: str) -> str:
    return textwrap.dedent(code).strip("\n")


QUESTIONS = [
    {
        "title": "回文判断",
        "description": "实现 is_palindrome(s)，判断字符串是否为回文。忽略大小写、空格和标点符号，只考虑字母和数字；空字符串视为回文。",
        "function_name": "is_palindrome",
        "signature": "def is_palindrome(s: str) -> bool",
        "starter_code": "def is_palindrome(s: str) -> bool:\n    # 在这里实现你的代码\n    pass\n",
        "public_cases": [
            {"args": ["A man, a plan, a canal: Panama"], "expected": True},
            {"args": ["race a car"], "expected": False},
            {"args": ["   "], "expected": True},
        ],
        "hidden_tests": "def test_legacy_placeholder():\n    assert True\n",
        "teacher_constraints": {
            "require_function": "is_palindrome",
            "ignore_case": True,
            "ignore_non_alnum": True,
            "empty_is_palindrome": True,
        },
        "reference_solution": (
            "def is_palindrome(s: str) -> bool:\n"
            "    cleaned = [ch.lower() for ch in s if ch.isalnum()]\n"
            "    return cleaned == cleaned[::-1]\n"
        ),
        "test_groups": [
            {
                "id": "F1",
                "name": "功能正确性",
                "dimension": "F",
                "max_score": 60,
                "tests": clean_tests(
                    """
                    def test_standard_cases():
                        assert is_palindrome("A man, a plan, a canal: Panama") is True
                        assert is_palindrome("race a car") is False
                        assert is_palindrome("abcba") is True

                    def test_case_and_punctuation():
                        assert is_palindrome("No 'x' in Nixon") is True
                        assert is_palindrome("Was it a car or a cat I saw?") is True
                        assert is_palindrome("hello") is False

                    def test_empty_and_whitespace():
                        assert is_palindrome("") is True
                        assert is_palindrome("   ") is True
                        assert is_palindrome("a") is True
                    """
                ),
            },
            {
                "id": "R1",
                "name": "鲁棒性与性能",
                "dimension": "R",
                "max_score": 10,
                "tests": clean_tests(
                    """
                    def test_unicode_and_numeric():
                        assert is_palindrome("上海自来水来自海上") is True
                        assert is_palindrome("12321") is True
                        assert is_palindrome("12345") is False
                        assert is_palindrome("A man, a plan, a canal: Panama!!!") is True

                    def test_long_input_performance():
                        s = "ab" * 5000 + "c" + "ba" * 5000
                        assert is_palindrome(s) is True
                    """
                ),
            },
        ],
        "score_cap_rules": [
            {
                "id": "HARDCODE",
                "condition_code": "hardcoded_public_examples",
                "cap": 20,
                "description": "硬编码公开样例时最高 20 分",
            }
        ],
    },
    {
        "title": "两数之和",
        "description": "实现 two_sum(nums, target)，返回两个下标 [i, j]，满足 nums[i] + nums[j] == target。题目保证恰好存在一个解，不能重复使用同一个元素，下标顺序不限。",
        "function_name": "two_sum",
        "signature": "def two_sum(nums: list[int], target: int) -> list[int]",
        "starter_code": "def two_sum(nums: list[int], target: int) -> list[int]:\n    # 在这里实现你的代码\n    return []\n",
        "public_cases": [
            {"args": [[2, 7, 11, 15], 9], "expected": [0, 1]},
            {"args": [[3, 2, 4], 6], "expected": [1, 2]},
            {"args": [[3, 3], 6], "expected": [0, 1]},
        ],
        "hidden_tests": "def test_legacy_placeholder():\n    assert True\n",
        "teacher_constraints": {
            "require_function": "two_sum",
            "complexity": "O(n)",
            "one_solution": True,
        },
        "reference_solution": (
            "def two_sum(nums: list[int], target: int) -> list[int]:\n"
            "    seen = {}\n"
            "    for i, num in enumerate(nums):\n"
            "        need = target - num\n"
            "        if need in seen:\n"
            "            return [seen[need], i]\n"
            "        seen[num] = i\n"
            "    return []\n"
        ),
        "test_groups": [
            {
                "id": "F1",
                "name": "功能正确性",
                "dimension": "F",
                "max_score": 60,
                "tests": clean_tests(
                    """
                    def _valid(result, nums, target):
                        assert isinstance(result, list)
                        assert len(result) == 2
                        i, j = result
                        assert i != j
                        assert nums[i] + nums[j] == target

                    def test_basic():
                        _valid(two_sum([2, 7, 11, 15], 9), [2, 7, 11, 15], 9)
                        _valid(two_sum([3, 2, 4], 6), [3, 2, 4], 6)

                    def test_duplicate_values():
                        _valid(two_sum([3, 3], 6), [3, 3], 6)
                        _valid(two_sum([1, 2, 3, 2], 4), [1, 2, 3, 2], 4)

                    def test_negative_and_zero():
                        _valid(two_sum([-3, 4, 3, 90], 0), [-3, 4, 3, 90], 0)
                        _valid(two_sum([0, 4, 3, 0], 0), [0, 4, 3, 0], 0)
                    """
                ),
            },
            {
                "id": "R1",
                "name": "鲁棒性与性能",
                "dimension": "R",
                "max_score": 10,
                "tests": clean_tests(
                    """
                    def _valid(result, nums, target):
                        assert isinstance(result, list)
                        assert len(result) == 2
                        i, j = result
                        assert i != j
                        assert nums[i] + nums[j] == target

                    def test_large_array_performance():
                        nums = list(range(20000))
                        _valid(two_sum(nums, 39997), nums, 39997)

                    def test_mixed_ints():
                        nums = [10**9, -10**9, 7, 3]
                        _valid(two_sum(nums, 0), nums, 0)
                        nums = [2, 5, 5, 11]
                        _valid(two_sum(nums, 10), nums, 10)
                    """
                ),
            },
        ],
        "score_cap_rules": [
            {
                "id": "NO_OPTIMAL",
                "condition_code": "required_complexity_missing",
                "cap": 30,
                "description": "未达到 O(n) 时间复杂度时最高 30 分",
            }
        ],
    },
    {
        "title": "有效括号",
        "description": "实现 valid_parentheses(s)，判断括号字符串是否有效。括号包括 ()、[]、{}，必须正确闭合且顺序正确；空字符串视为有效。",
        "function_name": "valid_parentheses",
        "signature": "def valid_parentheses(s: str) -> bool",
        "starter_code": "def valid_parentheses(s: str) -> bool:\n    # 在这里实现你的代码\n    return False\n",
        "public_cases": [
            {"args": ["()"], "expected": True},
            {"args": ["()[]{}"], "expected": True},
            {"args": ["(]"], "expected": False},
            {"args": ["([)]"], "expected": False},
        ],
        "hidden_tests": "def test_legacy_placeholder():\n    assert True\n",
        "teacher_constraints": {
            "require_function": "valid_parentheses",
            "must_use_stack": True,
        },
        "reference_solution": (
            "def valid_parentheses(s: str) -> bool:\n"
            "    pairs = {')': '(', ']': '[', '}': '{'}\n"
            "    stack = []\n"
            "    for ch in s:\n"
            "        if ch in pairs:\n"
            "            if not stack or stack[-1] != pairs[ch]:\n"
            "                return False\n"
            "            stack.pop()\n"
            "        else:\n"
            "            stack.append(ch)\n"
            "    return not stack\n"
        ),
        "test_groups": [
            {
                "id": "F1",
                "name": "功能正确性",
                "dimension": "F",
                "max_score": 60,
                "tests": clean_tests(
                    """
                    def test_valid_cases():
                        assert valid_parentheses("()") is True
                        assert valid_parentheses("()[]{}") is True
                        assert valid_parentheses("({[]})") is True

                    def test_invalid_cases():
                        assert valid_parentheses("(]") is False
                        assert valid_parentheses("([)]") is False
                        assert valid_parentheses("{") is False
                        assert valid_parentheses(")(") is False

                    def test_empty():
                        assert valid_parentheses("") is True
                    """
                ),
            },
            {
                "id": "R1",
                "name": "鲁棒性与性能",
                "dimension": "R",
                "max_score": 10,
                "tests": clean_tests(
                    """
                    def test_deep_nesting():
                        assert valid_parentheses("(" * 5000 + ")" * 5000) is True
                        assert valid_parentheses("(" * 5000 + "]" * 5000) is False

                    def test_long_mixed():
                        assert valid_parentheses("()[]{}()[]{}" * 1000) is True
                        assert valid_parentheses("((()))[]{}" * 1000) is True
                        assert valid_parentheses("((()))[]{}}" * 1000) is False
                    """
                ),
            },
        ],
        "score_cap_rules": [
            {
                "id": "NO_STACK",
                "condition_code": "required_algorithm_missing",
                "cap": 40,
                "description": "未使用栈算法时最高 40 分",
            }
        ],
    },
]


def api(method: str, path: str, token: str | None = None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers,
        timeout=300,
        **kwargs,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {resp.status_code}: {resp.text[:500]}")
    if resp.status_code == 204:
        return None
    return resp.json()


def find_by_title(items: list[dict], title: str) -> dict | None:
    return next((item for item in items if item.get("title") == title), None)


def main() -> int:
    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": TEACHER_USERNAME, "password": TEACHER_PASSWORD},
        timeout=30,
    )
    if login_resp.status_code != 200:
        raise RuntimeError(f"教师登录失败: {login_resp.status_code} {login_resp.text[:300]}")
    token = login_resp.json()["access_token"]

    courses = api("GET", "/courses", token, params={"page_size": 100})["items"]
    course = find_by_title(courses, COURSE_TITLE)
    if course is None:
        raise RuntimeError(f"未找到课程: {COURSE_TITLE}")
    course_id = course["id"]

    assignments = api(
        "GET", "/assignments", token,
        params={"course_id": course_id, "page_size": 100},
    )["items"]
    assignment = find_by_title(assignments, ASSIGNMENT_TITLE)
    if assignment is None:
        assignment = api(
            "POST", "/assignments", token,
            json={"course_id": course_id, "title": ASSIGNMENT_TITLE, "status": "draft"},
        )
        print(f"创建作业: {ASSIGNMENT_TITLE} (id={assignment['id']})")
    assignment_id = assignment["id"]

    existing_questions = api(
        "GET", f"/assignments/{assignment_id}/questions", token,
        params={"page_size": 100},
    )["items"]

    for qd in QUESTIONS:
        existing = find_by_title(existing_questions, qd["title"])
        if existing is None:
            created = api(
                "POST", f"/assignments/{assignment_id}/questions", token,
                json={
                    "title": qd["title"],
                    "description": qd["description"],
                    "function_name": qd["function_name"],
                    "signature": qd["signature"],
                    "starter_code": qd["starter_code"],
                    "public_cases": qd["public_cases"],
                    "hidden_tests": qd["hidden_tests"],
                    "time_limit_ms": 5000,
                    "memory_limit_mb": 128,
                    "grading_mode": "active",
                },
            )
            question_id = created["id"]
            print(f"创建题目: {qd['title']} (id={question_id})")
        else:
            question_id = existing["id"]
            print(f"复用题目: {qd['title']} (id={question_id})")

        api(
            "PUT", f"/ai-grading/questions/assignment/{question_id}/config", token,
            json={
                "grading_mode": "active",
                "teacher_constraints": qd["teacher_constraints"],
                "reference_solution": qd["reference_solution"],
                "test_groups": qd["test_groups"],
                "score_cap_rules": qd["score_cap_rules"],
            },
        )
        print(f"已写入 AI 配置: {qd['title']}")

    published = api("POST", f"/assignments/{assignment_id}/publish", token)
    print(f"作业已发布: {published['title']} (id={assignment_id}, status={published['status']})")
    print(f"学生端入口: http://localhost:5173/student/assignments/{assignment_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
