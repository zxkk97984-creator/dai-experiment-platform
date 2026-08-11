"""种子数据脚本 —— 为 DAI 实验平台插入全面的测试数据。

运行方式:
    cd backend && .venv\\Scripts\\python.exe -m app.seed_data

所有数据幂等：先按外键依赖顺序清除旧数据，再插入新数据。
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Assignment,
    AcademicTerm,
    Chapter,
    Course,
    CourseEnrollment,
    CourseTeachingClass,
    Exam,
    ExamAnswer,
    ExamGrade,
    ExamQuestion,
    ExamSubmission,
    ExperimentModule,
    ExperimentRecord,
    ExperimentSubmission,
    JudgeQuestion,
    Lesson,
    NotebookTemplate,
    NotebookTemplateVersion,
    Submission,
    TeachingClass,
    TeachingClassStudent,
    User,
)
from app.security import hash_password

# ── 常量 ────────────────────────────────────────────────────────

PASSWORD = "Test1234!"
HASHED_PASSWORD = hash_password(PASSWORD)

# 正确答案
CORRECT_ADD_TWO = "def add_two(a, b):\n    return a + b"
CORRECT_IS_PRIME = """def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True"""
CORRECT_FIBONACCI = """def fibonacci(n):
    if n <= 0:
        return []
    if n == 1:
        return [0]
    result = [0, 1]
    for i in range(2, n):
        result.append(result[-1] + result[-2])
    return result"""
CORRECT_REVERSE_STRING = "def reverse_string(s):\n    return s[::-1]"
CORRECT_UNIQUE_SORTED = "def unique_sorted(lst):\n    return sorted(list(set(lst)))"
CORRECT_WORD_COUNT = """def word_count(text):
    import re
    words = re.findall(r'\\w+', text.lower())
    result = {}
    for w in words:
        result[w] = result.get(w, 0) + 1
    return result"""
CORRECT_MATRIX_MULTIPLY = """def matrix_multiply(A, B):
    rows_A = len(A)
    cols_A = len(A[0])
    cols_B = len(B[0])
    result = [[0 for _ in range(cols_B)] for _ in range(rows_A)]
    for i in range(rows_A):
        for j in range(cols_B):
            for k in range(cols_A):
                result[i][j] += A[i][k] * B[k][j]
    return result"""

# 错误答案（bob 的 is_prime）
WRONG_IS_PRIME = "def is_prime(n):\n    return True"

# ── 辅助函数 ────────────────────────────────────────────────────

def _now() -> datetime:
    """返回当前 UTC 时间"""
    return datetime.now(timezone.utc)


def _clear_table(db: Session, model, *, skip_admin: bool = False):
    """清除表中所有数据，可选跳过 admin 用户"""
    if skip_admin and model is User:
        db.execute(delete(model).where(model.username != "admin"))
    else:
        db.execute(delete(model))
    db.flush()


# ── 1. 创建用户 ─────────────────────────────────────────────────

def create_users(db: Session) -> dict[str, User]:
    """创建 7 个用户（admin 已存在则跳过）。返回 {username: User} 映射"""
    print("[1/10] 清除旧数据...")
    # 按外键依赖顺序从子表到父表删除，确保幂等
    _clear_table(db, ExamAnswer)
    _clear_table(db, ExamGrade)
    _clear_table(db, ExamSubmission)
    _clear_table(db, ExperimentSubmission)
    _clear_table(db, ExperimentRecord)
    _clear_table(db, Submission)
    _clear_table(db, ExamQuestion)
    _clear_table(db, JudgeQuestion)
    _clear_table(db, Exam)
    _clear_table(db, Assignment)
    _clear_table(db, CourseEnrollment)
    _clear_table(db, CourseTeachingClass)
    _clear_table(db, TeachingClassStudent)
    _clear_table(db, Lesson)
    _clear_table(db, Chapter)
    _clear_table(db, Course)
    _clear_table(db, TeachingClass)
    _clear_table(db, AcademicTerm)
    _clear_table(db, ExperimentModule)

    # 解除 Notebook 模板和版本的循环外键
    # NotebookTemplate.current_version_id → NotebookTemplateVersion.id
    # NotebookTemplateVersion.template_id → NotebookTemplate.id
    # 方案：先设 current_version_id = NULL → 删版本 → 删模板
    db.execute(update(NotebookTemplate).values(current_version_id=None))
    db.flush()
    db.execute(delete(NotebookTemplateVersion))
    db.execute(delete(NotebookTemplate))

    # 最后删除用户（保留 admin）
    _clear_table(db, User, skip_admin=True)
    db.commit()
    print("  → 旧数据已清除")

    users: dict[str, User] = {}

    # 尝试获取 admin 用户，不存在则创建
    admin = db.query(User).filter(User.username == "admin").first()
    if admin is None:
        admin = User(
            username="admin",
            password_hash=HASHED_PASSWORD,
            real_name="系统管理员",
            role="admin",
        )
        db.add(admin)
        db.flush()
        print("  → 创建 admin 用户")
    else:
        print("  → admin 用户已存在，跳过")
    users["admin"] = admin

    # 其余用户列表
    user_defs = [
        ("teacher_john", "张教授", "teacher"),
        ("teacher_li", "李老师", "teacher"),
        ("student_alice", "爱丽丝", "student"),
        ("student_bob", "鲍勃", "student"),
        ("student_charlie", "查理", "student"),
        ("developer_wang", "王开发", "developer"),
    ]
    student_numbers = {"student_alice": "20260001", "student_bob": "20260002", "student_charlie": "20260003"}
    for username, real_name, role in user_defs:
        user = User(
            username=username,
            student_no=student_numbers.get(username),
            password_hash=HASHED_PASSWORD,
            real_name=real_name,
            role=role,
        )
        db.add(user)
        db.flush()
        users[username] = user
        print(f"  → 创建用户: {username} ({real_name}, {role})")

    db.commit()
    print("  ✓ 用户创建完成\n")
    return users


def create_academics(db: Session, users: dict[str, User]):
    print("[2/11] 创建学期、教学班与班级名单...")
    term = AcademicTerm(code="2026-FALL", name="2026 秋季学期", start_date=date(2026, 9, 1), end_date=date(2027, 1, 20), status="active")
    db.add(term); db.flush()
    class_a = TeachingClass(academic_term_id=term.id, code="CS-2601", name="计算机 2601 班", status="active")
    class_b = TeachingClass(academic_term_id=term.id, code="AI-2601", name="人工智能 2601 班", status="active")
    db.add_all([class_a, class_b]); db.flush()
    db.add_all([
        TeachingClassStudent(teaching_class_id=class_a.id, student_id=users["student_alice"].id, status="active"),
        TeachingClassStudent(teaching_class_id=class_a.id, student_id=users["student_bob"].id, status="active"),
        TeachingClassStudent(teaching_class_id=class_b.id, student_id=users["student_charlie"].id, status="active"),
    ])
    db.commit()
    print("  ✓ 教务基础数据创建完成\n")
    return {"term": term, "class_a": class_a, "class_b": class_b}


# ── 2. 创建模板与版本 ──────────────────────────────────────────

def create_templates(db: Session, users: dict[str, User]) -> dict[str, tuple[NotebookTemplate, NotebookTemplateVersion]]:
    """创建 3 个 Notebook 模板及其版本。返回 {name: (template, version)} 映射"""
    print("[2/10] 创建 Notebook 模板与版本...")

    developer = users["developer_wang"]
    teacher_john = users["teacher_john"]

    templates: dict[str, tuple[NotebookTemplate, NotebookTemplateVersion]] = {}

    # ── 模板1：Python基础实验 ──
    t1_draft_cells = [
        {"id": "c1", "type": "markdown", "source": "# Python 基础练习\n欢迎！", "order": 0, "student_editable": False, "source_hidden": False},
        {"id": "c2", "type": "code", "source": "# 写代码\nprint('Hello')", "order": 1, "student_editable": True, "source_hidden": False},
        {"id": "c3", "type": "code", "source": "import numpy as np\nimport pandas as pd", "order": 2, "student_editable": False, "source_hidden": True},
        {"id": "c4", "type": "markdown", "source": "## 练习1\n创建变量并打印", "order": 3, "student_editable": False, "source_hidden": False},
        {"id": "c5", "type": "code", "source": "# 练习1代码", "order": 4, "student_editable": True, "source_hidden": False},
    ]
    t1_cell_order = ["c1", "c2", "c3", "c4", "c5"]

    tpl1 = NotebookTemplate(
        name="Python基础实验",
        description="Python 基础语法练习模板",
        status="published",
        owner_id=developer.id,
        draft_cells=t1_draft_cells,
        draft_revision=1,
        draft_metadata={},
        draft_assets_dir=None,
    )
    db.add(tpl1)
    db.flush()

    ver1 = NotebookTemplateVersion(
        template_id=tpl1.id,
        version_number=1,
        sha256="sha256:seed-template-1-v1",
        cells=t1_draft_cells,
        cell_order=t1_cell_order,
        notebook_metadata={},
        assets_dir=None,
        published_by_id=developer.id,
    )
    db.add(ver1)
    db.flush()

    tpl1.current_version_id = ver1.id
    db.add(tpl1)
    db.flush()
    templates["Python基础实验"] = (tpl1, ver1)
    print(f"  → 模板1: {tpl1.name} (v1)")

    # ── 模板2：数据分析实验 ──
    t2_draft_cells = [
        {"id": "c1", "type": "markdown", "source": "# 数据分析入门", "order": 0, "student_editable": False, "source_hidden": False},
        {"id": "c2", "type": "code", "source": "import numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\nprint('环境就绪')", "order": 1, "student_editable": False, "source_hidden": True},
        {"id": "c3", "type": "markdown", "source": "## 任务：数据统计", "order": 2, "student_editable": False, "source_hidden": False},
        {"id": "c4", "type": "code", "source": "import numpy as np\ndata = np.array([1,2,3,4,5])\nprint(f'均值: {data.mean()}')", "order": 3, "student_editable": True, "source_hidden": False},
    ]
    t2_cell_order = ["c1", "c2", "c3", "c4"]

    tpl2 = NotebookTemplate(
        name="数据分析实验",
        description="使用 Python 进行数据分析练习",
        status="published",
        owner_id=developer.id,
        draft_cells=t2_draft_cells,
        draft_revision=1,
        draft_metadata={},
        draft_assets_dir=None,
    )
    db.add(tpl2)
    db.flush()

    ver2 = NotebookTemplateVersion(
        template_id=tpl2.id,
        version_number=1,
        sha256="sha256:seed-template-2-v1",
        cells=t2_draft_cells,
        cell_order=t2_cell_order,
        notebook_metadata={},
        assets_dir=None,
        published_by_id=developer.id,
    )
    db.add(ver2)
    db.flush()

    tpl2.current_version_id = ver2.id
    db.add(tpl2)
    db.flush()
    templates["数据分析实验"] = (tpl2, ver2)
    print(f"  → 模板2: {tpl2.name} (v1)")

    # ── 模板3：机器学习基础 ──
    t3_draft_cells = [
        {"id": "c1", "type": "markdown", "source": "# 机器学习入门", "order": 0, "student_editable": False, "source_hidden": False},
        {"id": "c2", "type": "code", "source": "import numpy as np\nfrom sklearn.datasets import make_classification\nprint('ML环境就绪')", "order": 1, "student_editable": False, "source_hidden": True},
        {"id": "c3", "type": "markdown", "source": "## 线性回归基础", "order": 2, "student_editable": False, "source_hidden": False},
        {"id": "c4", "type": "code", "source": "# 实现简单线性回归\nprint('Hello ML')", "order": 3, "student_editable": True, "source_hidden": False},
    ]
    t3_cell_order = ["c1", "c2", "c3", "c4"]

    tpl3 = NotebookTemplate(
        name="机器学习基础",
        description="机器学习入门模板，包含线性回归练习",
        status="published",
        owner_id=teacher_john.id,
        draft_cells=t3_draft_cells,
        draft_revision=1,
        draft_metadata={},
        draft_assets_dir=None,
    )
    db.add(tpl3)
    db.flush()

    ver3 = NotebookTemplateVersion(
        template_id=tpl3.id,
        version_number=1,
        sha256="sha256:seed-template-3-v1",
        cells=t3_draft_cells,
        cell_order=t3_cell_order,
        notebook_metadata={},
        assets_dir=None,
        published_by_id=teacher_john.id,
    )
    db.add(ver3)
    db.flush()

    tpl3.current_version_id = ver3.id
    db.add(tpl3)
    db.flush()
    templates["机器学习基础"] = (tpl3, ver3)
    print(f"  → 模板3: {tpl3.name} (v1)")

    db.commit()
    print("  ✓ 模板与版本创建完成\n")
    return templates


# ── 3. 创建课程/章节/课时 ────────────────────────────────────────

def create_courses(
    db: Session,
    users: dict[str, User],
    templates: dict[str, tuple[NotebookTemplate, NotebookTemplateVersion]],
    academics: dict,
) -> dict[str, dict]:
    """创建 2 门课程及章节、课时。返回课程引用字典"""
    print("[3/10] 创建课程/章节/课时...")

    teacher_john = users["teacher_john"]
    teacher_li = users["teacher_li"]
    tpl1, _ = templates["Python基础实验"]
    tpl2, _ = templates["数据分析实验"]
    tpl3, _ = templates["机器学习基础"]

    courses: dict[str, dict] = {}

    # ── 课程1：Python编程与算法实战 ──
    course1 = Course(
        title="Python编程与算法实战",
        description="从零开始学习 Python 编程，掌握数据结构与算法基础",
        status="published",
        teacher_id=teacher_john.id,
        academic_term_id=academics["term"].id,
    )
    db.add(course1)
    db.flush()
    db.add_all([
        CourseTeachingClass(course_id=course1.id, teaching_class_id=academics["class_a"].id),
        CourseTeachingClass(course_id=course1.id, teaching_class_id=academics["class_b"].id),
    ])

    # 第1章：Python入门
    ch1 = Chapter(
        course_id=course1.id,
        title="Python入门",
        order_index=0,
    )
    db.add(ch1)
    db.flush()

    db.add(Lesson(chapter_id=ch1.id, title="认识Python", content_type="markdown",
           content="# 认识Python\nPython是一种解释型语言...", order_index=0))
    db.add(Lesson(chapter_id=ch1.id, title="变量与数据类型", content_type="markdown",
           content="# 变量与数据类型\nPython支持多种数据类型...", order_index=1))
    db.add(Lesson(chapter_id=ch1.id, title="Python基础实验", content_type="notebook",
           template_id=tpl1.id, order_index=2))
    print("  → 课程1 第1章: Python入门 (3课时)")

    # 第2章：函数与数据结构
    ch2 = Chapter(
        course_id=course1.id,
        title="函数与数据结构",
        order_index=1,
    )
    db.add(ch2)
    db.flush()

    db.add(Lesson(chapter_id=ch2.id, title="函数的定义与调用", content_type="markdown",
           content="# 函数的定义与调用\n函数是组织代码的基本方式...", order_index=0))
    db.add(Lesson(chapter_id=ch2.id, title="列表与字典", content_type="markdown",
           content="# 列表与字典\n列表和字典是 Python 最常用的数据结构...", order_index=1))
    db.add(Lesson(chapter_id=ch2.id, title="数据分析实践", content_type="notebook",
           template_id=tpl2.id, order_index=2))
    print("  → 课程1 第2章: 函数与数据结构 (3课时)")

    # 第3章：算法基础
    ch3 = Chapter(
        course_id=course1.id,
        title="算法基础",
        order_index=2,
    )
    db.add(ch3)
    db.flush()

    db.add(Lesson(chapter_id=ch3.id, title="排序算法概述", content_type="markdown",
           content="# 排序算法\n冒泡排序、快速排序...", order_index=0))
    db.add(Lesson(chapter_id=ch3.id, title="搜索算法", content_type="markdown",
           content="# 搜索算法\n二分查找、广度优先...", order_index=1))
    print("  → 课程1 第3章: 算法基础 (2课时)")

    courses["Python编程与算法实战"] = {"course": course1}
    db.flush()

    # ── 课程2：机器学习导论 ──
    course2 = Course(
        title="机器学习导论",
        description="机器学习基础知识与实战技能",
        status="published",
        teacher_id=teacher_li.id,
        academic_term_id=academics["term"].id,
    )
    db.add(course2)
    db.flush()
    db.add(CourseTeachingClass(course_id=course2.id, teaching_class_id=academics["class_a"].id))

    ch4 = Chapter(
        course_id=course2.id,
        title="数学基础",
        order_index=0,
    )
    db.add(ch4)
    db.flush()

    db.add(Lesson(chapter_id=ch4.id, title="线性代数回顾", content_type="markdown",
           content="# 线性代数回顾\n向量、矩阵、特征值...", order_index=0))
    db.add(Lesson(chapter_id=ch4.id, title="概率论基础", content_type="markdown",
           content="# 概率论基础\n条件概率、贝叶斯定理...", order_index=1))
    db.add(Lesson(chapter_id=ch4.id, title="机器学习实战", content_type="notebook",
           template_id=tpl3.id, order_index=2))
    print("  → 课程2 第1章: 数学基础 (3课时)")

    courses["机器学习导论"] = {"course": course2}

    db.commit()
    print("  ✓ 课程创建完成\n")
    return courses


# ── 4. 选课 ─────────────────────────────────────────────────────

def create_enrollments(db: Session, users: dict[str, User], courses: dict[str, dict]):
    """三个学生选课到两门课程"""
    print("[4/10] 创建选课记录...")

    students = ["student_alice", "student_bob", "student_charlie"]
    course_names = ["Python编程与算法实战", "机器学习导论"]

    for username in students:
        student = users[username]
        for course_name in course_names:
            course = courses[course_name]["course"]
            enrollment = CourseEnrollment(
                course_id=course.id,
                student_id=student.id,
                status="enrolled",
                origin="class",
            )
            db.add(enrollment)
            print(f"  → {username} 选课: {course_name}")

    db.commit()
    print("  ✓ 选课完成\n")


# ── 5. 创建作业与题目 ──────────────────────────────────────────

def create_assignments_and_questions(
    db: Session,
    users: dict[str, User],
    courses: dict[str, dict],
) -> dict[str, list[JudgeQuestion]]:
    """创建 3 个作业及其题目。返回 {作业标识: [题目的列表]} 映射"""
    print("[5/10] 创建作业与题目...")

    course1 = courses["Python编程与算法实战"]["course"]
    course2 = courses["机器学习导论"]["course"]
    teacher_john = users["teacher_john"]

    questions_map: dict[str, list[JudgeQuestion]] = {}

    # ── 作业1：Python基础编程 ──
    assignment1 = Assignment(
        course_id=course1.id,
        title="Python基础编程",
        description="掌握 Python 基本语法：函数定义、循环、条件判断等",
        status="published",
        created_by_id=teacher_john.id,
    )
    db.add(assignment1)
    db.flush()

    # 题目1-1：两数之和
    q1_1 = JudgeQuestion(
        assignment_id=assignment1.id,
        title="两数之和",
        description="编写函数add_two(a, b)，计算两个整数的和并返回。",
        function_name="add_two",
        signature="def add_two(a: int, b: int) -> int:",
        starter_code="def add_two(a, b):\n    # 在这里写你的代码\n    pass",
        public_cases=[{"args": [1, 2], "expected": 3}, {"args": [-5, 10], "expected": 5}],
        hidden_tests="""import pytest
import user_code

def test_add_two_positive():
    assert user_code.add_two(1, 2) == 3

def test_add_two_negative():
    assert user_code.add_two(-5, 10) == 5

def test_add_two_zero():
    assert user_code.add_two(0, 0) == 0

def test_add_two_large():
    assert user_code.add_two(1000, 2000) == 3000

def test_add_two_floats():
    assert user_code.add_two(3, 7) == 10""",
        time_limit_ms=5000,
        memory_limit_mb=128,
        max_attempts=5,
    )
    db.add(q1_1)

    # 题目1-2：判断素数
    q1_2 = JudgeQuestion(
        assignment_id=assignment1.id,
        title="判断素数",
        description="判断一个正整数是否为素数。是返回True，否则返回False。注意：1不是素数。",
        function_name="is_prime",
        signature="def is_prime(n: int) -> bool:",
        starter_code="def is_prime(n):\n    pass",
        public_cases=[{"args": [7], "expected": True}, {"args": [10], "expected": False}],
        hidden_tests="""import pytest
import user_code

def test_is_prime_2():
    assert user_code.is_prime(2) == True

def test_is_prime_1():
    assert user_code.is_prime(1) == False

def test_is_prime_7():
    assert user_code.is_prime(7) == True

def test_is_prime_97():
    assert user_code.is_prime(97) == True

def test_is_prime_even():
    assert user_code.is_prime(100) == False

def test_is_prime_large_non_prime():
    assert user_code.is_prime(9999) == False""",
        time_limit_ms=5000,
        memory_limit_mb=128,
        max_attempts=3,
    )
    db.add(q1_2)

    # 题目1-3：斐波那契数列
    q1_3 = JudgeQuestion(
        assignment_id=assignment1.id,
        title="斐波那契数列",
        description="返回斐波那契数列的前n项（列表形式）。n>=1。F(0)=0, F(1)=1。",
        function_name="fibonacci",
        signature="def fibonacci(n: int) -> list:",
        starter_code="def fibonacci(n):\n    pass",
        public_cases=[{"args": [5], "expected": [0, 1, 1, 2, 3]}, {"args": [1], "expected": [0]}],
        hidden_tests="""import pytest
import user_code

def test_fibonacci_5():
    assert user_code.fibonacci(5) == [0, 1, 1, 2, 3]

def test_fibonacci_1():
    assert user_code.fibonacci(1) == [0]

def test_fibonacci_2():
    assert user_code.fibonacci(2) == [0, 1]

def test_fibonacci_10_len():
    assert len(user_code.fibonacci(10)) == 10
    assert user_code.fibonacci(10)[-1] == 34""",
        time_limit_ms=5000,
        memory_limit_mb=128,
        max_attempts=5,
    )
    db.add(q1_3)

    # 题目1-4：字符串反转
    q1_4 = JudgeQuestion(
        assignment_id=assignment1.id,
        title="字符串反转",
        description="将输入字符串反转后返回。",
        function_name="reverse_string",
        signature="def reverse_string(s: str) -> str:",
        starter_code="def reverse_string(s):\n    pass",
        public_cases=[{"args": ["hello"], "expected": "olleh"}, {"args": [""], "expected": ""}],
        hidden_tests="""import pytest
import user_code

def test_normal():
    assert user_code.reverse_string("hello") == "olleh"

def test_empty():
    assert user_code.reverse_string("") == ""

def test_single():
    assert user_code.reverse_string("a") == "a"

def test_palindrome():
    assert user_code.reverse_string("aba") == "aba"

def test_unicode():
    assert user_code.reverse_string("你好世界") == "界世好你"
""",
        time_limit_ms=5000,
        memory_limit_mb=128,
        max_attempts=5,
    )
    db.add(q1_4)

    db.flush()
    questions_map["1"] = [q1_1, q1_2, q1_3, q1_4]
    print("  → 作业1: Python基础编程 (4题)")

    # ── 作业2：数据结构挑战 ──
    assignment2 = Assignment(
        course_id=course1.id,
        title="数据结构挑战",
        description="掌握 Python 列表、字典、字符串等数据结构的操作",
        status="published",
        created_by_id=teacher_john.id,
    )
    db.add(assignment2)
    db.flush()

    # 题目2-1：列表去重排序
    q2_1 = JudgeQuestion(
        assignment_id=assignment2.id,
        title="列表去重排序",
        description="去除列表中重复元素并按升序排序返回新列表。",
        function_name="unique_sorted",
        signature="def unique_sorted(lst: list) -> list:",
        starter_code="def unique_sorted(lst):\n    pass",
        public_cases=[{"args": [[3, 1, 2, 1, 3]], "expected": [1, 2, 3]}],
        hidden_tests="""import pytest
import user_code

def test_normal():
    assert user_code.unique_sorted([3, 1, 2, 1, 3]) == [1, 2, 3]

def test_empty():
    assert user_code.unique_sorted([]) == []

def test_already_sorted():
    assert user_code.unique_sorted([1, 2, 3]) == [1, 2, 3]

def test_reverse():
    assert user_code.unique_sorted([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]

def test_all_same():
    assert user_code.unique_sorted([7, 7, 7, 7]) == [7]""",
        time_limit_ms=5000,
        memory_limit_mb=128,
        max_attempts=5,
    )
    db.add(q2_1)

    # 题目2-2：词频统计
    q2_2 = JudgeQuestion(
        assignment_id=assignment2.id,
        title="词频统计",
        description="统计文本中每个单词出现次数（忽略大小写和标点符号），返回字典。",
        function_name="word_count",
        signature="def word_count(text: str) -> dict:",
        starter_code="def word_count(text):\n    pass",
        public_cases=[{"args": ["Hello world Hello"], "expected": {"hello": 2, "world": 1}}],
        hidden_tests=r"""import pytest
import user_code

def test_simple():
    result = user_code.word_count("Hello world Hello")
    assert result == {"hello": 2, "world": 1}

def test_empty():
    assert user_code.word_count("") == {}

def test_punctuation():
    result = user_code.word_count("Hello, world! Hello.")
    assert result.get("hello") == 2
    assert result.get("world") == 1

def test_case():
    result = user_code.word_count("HELLO hello HeLLo")
    assert result == {"hello": 3}""",
        time_limit_ms=5000,
        memory_limit_mb=128,
        max_attempts=5,
    )
    db.add(q2_2)

    db.flush()
    questions_map["2"] = [q2_1, q2_2]
    print("  → 作业2: 数据结构挑战 (2题)")

    # ── 作业3：机器学习概念 ──
    assignment3 = Assignment(
        course_id=course2.id,
        title="机器学习概念",
        description="矩阵运算等机器学习基础编程练习",
        status="published",
        created_by_id=users["teacher_li"].id,
    )
    db.add(assignment3)
    db.flush()

    # 题目3-1：矩阵乘法
    q3_1 = JudgeQuestion(
        assignment_id=assignment3.id,
        title="矩阵乘法",
        description="实现两个矩阵的乘法，返回结果矩阵。假设输入总是合法的（A的列数等于B的行数）。",
        function_name="matrix_multiply",
        signature="def matrix_multiply(A: list, B: list) -> list:",
        starter_code="def matrix_multiply(A, B):\n    pass",
        public_cases=[{"args": [[[1, 2], [3, 4]], [[5, 6], [7, 8]]], "expected": [[19, 22], [43, 50]]}],
        hidden_tests="""import pytest
import user_code

def test_2x2():
    A = [[1, 2], [3, 4]]
    B = [[5, 6], [7, 8]]
    assert user_code.matrix_multiply(A, B) == [[19, 22], [43, 50]]

def test_identity():
    A = [[1, 0], [0, 1]]
    B = [[5, 6], [7, 8]]
    assert user_code.matrix_multiply(A, B) == [[5, 6], [7, 8]]

def test_1x1():
    assert user_code.matrix_multiply([[3]], [[4]]) == [[12]]

def test_rectangular():
    A = [[1, 2, 3], [4, 5, 6]]
    B = [[7, 8], [9, 10], [11, 12]]
    expected = [[1*7+2*9+3*11, 1*8+2*10+3*12], [4*7+5*9+6*11, 4*8+5*10+6*12]]
    assert user_code.matrix_multiply(A, B) == expected""",
        time_limit_ms=5000,
        memory_limit_mb=128,
        max_attempts=5,
    )
    db.add(q3_1)

    db.flush()
    questions_map["3"] = [q3_1]
    print("  → 作业3: 机器学习概念 (1题)")

    db.commit()
    print("  ✓ 作业与题目创建完成\n")
    return questions_map


# ── 6. 创建提交记录 ─────────────────────────────────────────────

def create_submissions(
    db: Session,
    users: dict[str, User],
    questions_map: dict[str, list[JudgeQuestion]],
):
    """创建作业提交记录"""
    print("[6/10] 创建提交记录...")

    alice = users["student_alice"]
    bob = users["student_bob"]

    submissions_data = [
        # Alice 全对
        (alice, questions_map["1"][0], "accepted", 100, CORRECT_ADD_TWO),
        (alice, questions_map["1"][1], "accepted", 100, CORRECT_IS_PRIME),
        (alice, questions_map["1"][2], "accepted", 100, CORRECT_FIBONACCI),
        (alice, questions_map["1"][3], "accepted", 100, CORRECT_REVERSE_STRING),
        # Bob 部分
        (bob, questions_map["1"][0], "accepted", 100, CORRECT_ADD_TWO),
        (bob, questions_map["1"][1], "wrong_answer", 0, WRONG_IS_PRIME),
        # Alice 作业2
        (alice, questions_map["2"][0], "accepted", 100, CORRECT_UNIQUE_SORTED),
        (alice, questions_map["2"][1], "accepted", 100, CORRECT_WORD_COUNT),
        # Bob 作业2
        (bob, questions_map["2"][0], "accepted", 100, CORRECT_UNIQUE_SORTED),
        # Alice 作业3
        (alice, questions_map["3"][0], "accepted", 100, CORRECT_MATRIX_MULTIPLY),
    ]

    for student, question, status, score, code in submissions_data:
        sub = Submission(
            question_id=question.id,
            student_id=student.id,
            code=code,
            status=status,
            score=score,
        )
        db.add(sub)
        print(f"  → {student.username} 提交 {question.title}: {status} ({score}分)")

    db.commit()
    print("  ✓ 提交记录创建完成\n")


# ── 7. 创建考试与题目 ───────────────────────────────────────────

def create_exams_and_questions(
    db: Session,
    users: dict[str, User],
    courses: dict[str, dict],
) -> dict[str, dict]:
    """创建 2 个考试及其题目。返回 {考试标题: {exam, questions}} 映射"""
    print("[7/10] 创建考试与题目...")

    course1 = courses["Python编程与算法实战"]["course"]

    exams_map: dict[str, dict] = {}

    # ── 考试1：Python期中测验 ──
    exam1 = Exam(
        course_id=course1.id,
        title="Python期中测验",
        status="published",
        duration_minutes=60,
        created_by_id=users["teacher_john"].id,
    )
    db.add(exam1)
    db.flush()

    eq1_questions: list[ExamQuestion] = []

    # 题1: 单选题 - 定义函数关键字
    q1 = ExamQuestion(
        exam_id=exam1.id,
        question_type="single_choice",
        prompt="Python中定义函数的关键字是？",
        options={"A": "def", "B": "function", "C": "func", "D": "define"},
        correct_answer={"correct": ["A"]},
        points=10,
        order_index=0,
    )
    db.add(q1)
    eq1_questions.append(q1)

    # 题2: 单选题 - 可变数据类型
    q2 = ExamQuestion(
        exam_id=exam1.id,
        question_type="single_choice",
        prompt="以下哪个是可变数据类型？",
        options={"A": "int", "B": "str", "C": "list", "D": "tuple"},
        correct_answer={"correct": ["C"]},
        points=10,
        order_index=1,
    )
    db.add(q2)
    eq1_questions.append(q2)

    # 题3: 多选题 - Python内置数据类型
    q3 = ExamQuestion(
        exam_id=exam1.id,
        question_type="multi_choice",
        prompt="以下哪些是Python内置数据类型？（多选）",
        options={"A": "list", "B": "dict", "C": "array", "D": "tuple"},
        correct_answer={"correct": ["A", "B", "D"]},
        points=15,
        order_index=2,
    )
    db.add(q3)
    eq1_questions.append(q3)

    # 题4: 多选题 - 列表添加元素方法
    q4 = ExamQuestion(
        exam_id=exam1.id,
        question_type="multi_choice",
        prompt="哪些方法可以给列表添加元素？（多选）",
        options={"A": "append", "B": "extend", "C": "add", "D": "insert"},
        correct_answer={"correct": ["A", "B", "D"]},
        points=15,
        order_index=3,
    )
    db.add(q4)
    eq1_questions.append(q4)

    # 题5: 编程题 - 两数之和
    q5 = ExamQuestion(
        exam_id=exam1.id,
        question_type="code",
        prompt="编写函数add_two(a, b)，计算两个整数的和并返回。",
        options=None,
        correct_answer={"correct": []},
        points=25,
        order_index=4,
        starter_code="def add_two(a, b):\n    # 在这里写你的代码\n    pass",
        public_cases=[{"args": [1, 2], "expected": 3}, {"args": [-5, 10], "expected": 5}],
        hidden_tests="""import pytest
import user_code

def test_add_two_positive():
    assert user_code.add_two(1, 2) == 3

def test_add_two_negative():
    assert user_code.add_two(-5, 10) == 5

def test_add_two_zero():
    assert user_code.add_two(0, 0) == 0

def test_add_two_large():
    assert user_code.add_two(1000, 2000) == 3000

def test_add_two_floats():
    assert user_code.add_two(3, 7) == 10""",
        time_limit_ms=5000,
        memory_limit_mb=128,
    )
    db.add(q5)
    eq1_questions.append(q5)

    # 题6: 编程题 - 字符串反转
    q6 = ExamQuestion(
        exam_id=exam1.id,
        question_type="code",
        prompt="编写函数reverse_string(s)，将输入字符串反转后返回。",
        options=None,
        correct_answer={"correct": []},
        points=25,
        order_index=5,
        starter_code="def reverse_string(s):\n    pass",
        public_cases=[{"args": ["hello"], "expected": "olleh"}, {"args": [""], "expected": ""}],
        hidden_tests="""import pytest
import user_code

def test_normal():
    assert user_code.reverse_string("hello") == "olleh"

def test_empty():
    assert user_code.reverse_string("") == ""

def test_single():
    assert user_code.reverse_string("a") == "a"

def test_palindrome():
    assert user_code.reverse_string("aba") == "aba"

def test_unicode():
    assert user_code.reverse_string("你好世界") == "界世好你"
""",
        time_limit_ms=5000,
        memory_limit_mb=128,
    )
    db.add(q6)
    eq1_questions.append(q6)

    db.flush()
    exams_map["Python期中测验"] = {"exam": exam1, "questions": eq1_questions}
    print("  → 考试1: Python期中测验 (6题, 60分钟)")

    # ── 考试2：数据结构测试 ──
    exam2 = Exam(
        course_id=course1.id,
        title="数据结构测试",
        status="published",
        duration_minutes=45,
        created_by_id=users["teacher_john"].id,
    )
    db.add(exam2)
    db.flush()

    eq2_questions: list[ExamQuestion] = []

    # 题1: 单选题 - 列表索引
    q1_e2 = ExamQuestion(
        exam_id=exam2.id,
        question_type="single_choice",
        prompt="列表的索引从什么开始？",
        options={"A": "-1", "B": "0", "C": "1", "D": "随机"},
        correct_answer={"correct": ["B"]},
        points=15,
        order_index=0,
    )
    db.add(q1_e2)
    eq2_questions.append(q1_e2)

    # 题2: 单选题 - 字典获取值
    q2_e2 = ExamQuestion(
        exam_id=exam2.id,
        question_type="single_choice",
        prompt="字典中获取值的方法是？",
        options={"A": "dict.key", "B": "dict[key]", "C": "dict->key", "D": "dict.value(key)"},
        correct_answer={"correct": ["B"]},
        points=15,
        order_index=1,
    )
    db.add(q2_e2)
    eq2_questions.append(q2_e2)

    # 题3: 编程题 - 列表去重排序
    q3_e2 = ExamQuestion(
        exam_id=exam2.id,
        question_type="code",
        prompt="编写函数unique_sorted(lst)，去除列表中重复元素并按升序排序返回新列表。",
        options=None,
        correct_answer={"correct": []},
        points=30,
        order_index=2,
        starter_code="def unique_sorted(lst):\n    pass",
        public_cases=[{"args": [[3, 1, 2, 1, 3]], "expected": [1, 2, 3]}],
        hidden_tests="""import pytest
import user_code

def test_normal():
    assert user_code.unique_sorted([3, 1, 2, 1, 3]) == [1, 2, 3]

def test_empty():
    assert user_code.unique_sorted([]) == []

def test_already_sorted():
    assert user_code.unique_sorted([1, 2, 3]) == [1, 2, 3]

def test_reverse():
    assert user_code.unique_sorted([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]

def test_all_same():
    assert user_code.unique_sorted([7, 7, 7, 7]) == [7]""",
        time_limit_ms=5000,
        memory_limit_mb=128,
    )
    db.add(q3_e2)
    eq2_questions.append(q3_e2)

    db.flush()
    exams_map["数据结构测试"] = {"exam": exam2, "questions": eq2_questions}
    print("  → 考试2: 数据结构测试 (3题, 45分钟)")

    db.commit()
    print("  ✓ 考试与题目创建完成\n")
    return exams_map


# ── 8. 创建考试提交与答案 ───────────────────────────────────────

def create_exam_submissions_and_answers(
    db: Session,
    users: dict[str, User],
    exams_map: dict[str, dict],
):
    """创建考试提交记录与答案"""
    print("[8/10] 创建考试提交与答案...")

    alice = users["student_alice"]
    now = _now()

    # ── Alice 考试1：已完成并评分 ──
    exam1_data = exams_map["Python期中测验"]
    exam1 = exam1_data["exam"]
    eq1_questions = exam1_data["questions"]

    started_at_1 = now - timedelta(hours=2)
    expires_at_1 = started_at_1 + timedelta(minutes=exam1.duration_minutes)
    submitted_at_1 = started_at_1 + timedelta(minutes=45)
    graded_at_1 = submitted_at_1 + timedelta(minutes=5)

    sub1 = ExamSubmission(
        exam_id=exam1.id,
        student_id=alice.id,
        status="graded",
        score=100,
        started_at=started_at_1,
        expires_at=expires_at_1,
        submitted_at=submitted_at_1,
        graded_at=graded_at_1,
    )
    db.add(sub1)
    db.flush()

    # 逐题答案
    answers_data_1 = [
        # 题1：单选
        {"question": eq1_questions[0], "selected_options": ["A"], "score": 10, "grading_status": "completed", "code_answer": None},
        # 题2：单选
        {"question": eq1_questions[1], "selected_options": ["C"], "score": 10, "grading_status": "completed", "code_answer": None},
        # 题3：多选
        {"question": eq1_questions[2], "selected_options": ["A", "B", "D"], "score": 15, "grading_status": "completed", "code_answer": None},
        # 题4：多选
        {"question": eq1_questions[3], "selected_options": ["A", "B", "D"], "score": 15, "grading_status": "completed", "code_answer": None},
        # 题5：编程题
        {"question": eq1_questions[4], "selected_options": None, "score": 25, "grading_status": "completed", "code_answer": CORRECT_ADD_TWO},
        # 题6：编程题
        {"question": eq1_questions[5], "selected_options": None, "score": 25, "grading_status": "completed", "code_answer": CORRECT_REVERSE_STRING},
    ]
    for ans in answers_data_1:
        answer = ExamAnswer(
            submission_id=sub1.id,
            question_id=ans["question"].id,
            selected_options=ans["selected_options"],
            code_answer=ans["code_answer"],
            score=ans["score"],
            grading_status=ans["grading_status"],
        )
        db.add(answer)

    # 考试成绩
    grade1 = ExamGrade(
        exam_id=exam1.id,
        student_id=alice.id,
        score=100,
    )
    db.add(grade1)
    print("  → Alice 考试1: Python期中测验 (graded, 100分)")

    # ── Alice 考试2：进行中 ──
    exam2_data = exams_map["数据结构测试"]
    exam2 = exam2_data["exam"]
    eq2_questions = exam2_data["questions"]

    started_at_2 = now - timedelta(minutes=10)
    expires_at_2 = started_at_2 + timedelta(minutes=exam2.duration_minutes)

    sub2 = ExamSubmission(
        exam_id=exam2.id,
        student_id=alice.id,
        status="started",
        score=None,
        started_at=started_at_2,
        expires_at=expires_at_2,
    )
    db.add(sub2)
    db.flush()

    answers_data_2 = [
        # 题1：单选（已选B）
        {"question": eq2_questions[0], "selected_options": ["B"], "score": None, "grading_status": "pending", "code_answer": None},
        # 题2：单选（已选B）
        {"question": eq2_questions[1], "selected_options": ["B"], "score": None, "grading_status": "pending", "code_answer": None},
        # 题3：编程题（未作答）
        {"question": eq2_questions[2], "selected_options": None, "score": None, "grading_status": "pending", "code_answer": None},
    ]
    for ans in answers_data_2:
        answer = ExamAnswer(
            submission_id=sub2.id,
            question_id=ans["question"].id,
            selected_options=ans["selected_options"],
            code_answer=ans["code_answer"],
            score=ans["score"],
            grading_status=ans["grading_status"],
        )
        db.add(answer)

    print("  → Alice 考试2: 数据结构测试 (started, 进行中)")

    db.commit()
    print("  ✓ 考试提交与答案创建完成\n")


# ── 9. 创建实验模块 ────────────────────────────────────────────

def create_modules(
    db: Session,
    users: dict[str, User],
    templates: dict[str, tuple[NotebookTemplate, NotebookTemplateVersion]],
) -> dict[str, ExperimentModule]:
    """创建 2 个实验模块。返回 {名称: ExperimentModule} 映射"""
    print("[9/10] 创建实验模块...")

    developer = users["developer_wang"]
    tpl1, _ = templates["Python基础实验"]
    tpl2, _ = templates["数据分析实验"]

    modules: dict[str, ExperimentModule] = {}

    # 模块1
    mod1 = ExperimentModule(
        name="Python基础实验",
        description="练习Python基本语法",
        template_id=tpl1.id,
        owner_id=developer.id,
        status="published",
    )
    db.add(mod1)
    modules["Python基础实验"] = mod1
    print(f"  → 模块1: {mod1.name}")

    # 模块2
    mod2 = ExperimentModule(
        name="数据分析入门",
        description="学习使用Python进行数据分析",
        template_id=tpl2.id,
        owner_id=developer.id,
        status="published",
    )
    db.add(mod2)
    modules["数据分析入门"] = mod2
    print(f"  → 模块2: {mod2.name}")

    db.commit()
    print("  ✓ 实验模块创建完成\n")
    return modules


# ── 10. 创建实验记录 ────────────────────────────────────────────

def create_experiment_records(
    db: Session,
    users: dict[str, User],
    templates: dict[str, tuple[NotebookTemplate, NotebookTemplateVersion]],
    modules: dict[str, ExperimentModule],
):
    """创建实验记录"""
    print("[10/10] 创建实验记录...")

    alice = users["student_alice"]
    tpl1, ver1 = templates["Python基础实验"]
    mod1 = modules["Python基础实验"]

    # 从模板版本 cells 中提取 code cell 的 source
    cells_sources: dict = {}
    for cell in ver1.cells:
        cells_sources[cell["id"]] = cell["source"]

    # 模拟 cells_outputs（c2 的 stdout 输出）
    cells_outputs: dict = {
        "c2": {
            "outputs": [
                {"msg_type": "stream", "content": {"name": "stdout", "text": "Hello\n"}}
            ],
            "execution_count": 1,
        }
    }

    record = ExperimentRecord(
        module_id=mod1.id,
        lesson_id=None,  # 使用模块入口，lesson_id 保持空
        template_version_id=ver1.id,
        student_id=alice.id,
        status="started",
        cells_sources=cells_sources,
        cells_outputs=cells_outputs,
        started_at=_now(),
    )
    db.add(record)
    db.flush()
    print(f"  → Alice 的模块1实验记录 (status=started, {len(cells_sources)} 个 cell)")

    db.commit()
    print("  ✓ 实验记录创建完成\n")


# ── 主入口 ──────────────────────────────────────────────────────

def main():
    """运行种子数据脚本"""
    print("=" * 60)
    print("DAI 实验平台 —— 种子数据脚本")
    print("=" * 60)
    print()

    db: Session = SessionLocal()
    try:
        # 1. 用户
        users = create_users(db)

        academics = create_academics(db, users)

        # 2. 模板与版本
        templates = create_templates(db, users)

        # 3. 课程/章节/课时
        courses = create_courses(db, users, templates, academics)

        # 4. 选课
        create_enrollments(db, users, courses)

        # 5. 作业与题目
        questions_map = create_assignments_and_questions(db, users, courses)

        # 6. 提交记录
        create_submissions(db, users, questions_map)

        # 7. 考试与题目
        exams_map = create_exams_and_questions(db, users, courses)

        # 8. 考试提交与答案
        create_exam_submissions_and_answers(db, users, exams_map)

        # 9. 实验模块
        modules = create_modules(db, users, templates)

        # 10. 实验记录
        create_experiment_records(db, users, templates, modules)

        print("=" * 60)
        print("✅ 种子数据插入完成！")
        print("=" * 60)
        print()
        print("账户汇总：")
        print("  管理员:   admin / Test1234!")
        print("  教师:     teacher_john / Test1234!  (张教授)")
        print("  教师:     teacher_li / Test1234!    (李老师)")
        print("  学生:     student_alice / Test1234! (爱丽丝)")
        print("  学生:     student_bob / Test1234!   (鲍勃)")
        print("  学生:     student_charlie / Test1234! (查理)")
        print("  开发者:   developer_wang / Test1234! (王开发)")

    except Exception as e:
        db.rollback()
        print(f"❌ 错误: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
