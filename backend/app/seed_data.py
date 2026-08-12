"""生产前内测全量种子数据。

运行前提：

1. 已执行 ``python -m app.cli seed-environments --enqueue``；
2. ``basic``、``data``、``torch-cpu`` 三个环境的可用版本均已构建完成；
3. 当前环境不是 production；
4. 显式确认这是一次可清理业务数据的内测重置：

   ``python -m app.seed_data --confirm-internal-reset``

脚本会清理业务演示数据，但保留管理员账号和环境控制面数据。所有生成内容
来自固定数据目录与固定随机种子，重复执行不会产生重复账号或重复资源。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, SessionLocal
from app.models import (
    AcademicTerm,
    Assignment,
    Chapter,
    Course,
    CourseEnrollment,
    CourseTeachingClass,
    EnvironmentProfile,
    EnvironmentVersion,
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
    QuestionRubric,
    Submission,
    TeachingClass,
    TeachingClassStudent,
    User,
)
from app.security import hash_password


SEED_RANDOM_SEED = 20260811
DEFAULT_PASSWORD = "Test1234!"
TYPICAL_COURSE_TITLE = "[典型] Python 与 AI 实验全流程"
ENVIRONMENT_SLUGS = ("basic", "data", "torch-cpu")
PRESERVED_TABLES = {
    "package_catalog",
    "environment_profiles",
    "environment_versions",
    "profile_version_packages",
    "environment_build_jobs",
}
CLASS_PREFIXES = [f"246216{i:02d}" for i in range(10)]


TEACHER_DEFS = [
    ("teacher_zhang", "张明远", "teacher"),
    ("teacher_chen", "陈思远", "teacher"),
    ("teacher_zhao", "赵清禾", "teacher"),
]


COURSE_CATALOG: dict[str, list[tuple[str, str, bool]]] = {
    "teacher_zhang": [
        (TYPICAL_COURSE_TITLE, "python", True),
        ("Python 程序设计基础", "python", False),
        ("数据结构与算法实战", "algorithm", False),
        ("软件工程与代码质量", "engineering", False),
        ("Web API 开发入门", "engineering", False),
        ("数据处理与可视化", "data", False),
        ("机器学习基础", "ml", False),
        ("深度学习入门", "torch", False),
        ("实验设计与效果评测", "engineering", False),
        ("AI 应用项目实战", "torch", False),
    ],
    "teacher_chen": [
        ("数据分析方法论", "data", False),
        ("NumPy 科学计算", "data", False),
        ("Pandas 数据工程", "data", False),
        ("统计学习基础", "ml", False),
        ("机器学习模型评估", "ml", False),
        ("特征工程与数据治理", "data", False),
        ("推荐系统原理", "ml", False),
        ("时间序列分析", "data", False),
        ("可解释机器学习", "ml", False),
        ("数据驱动的产品实验", "data", False),
    ],
    "teacher_zhao": [
        ("PyTorch 张量编程", "torch", False),
        ("神经网络与反向传播", "torch", False),
        ("计算机视觉基础", "torch", False),
        ("自然语言处理入门", "torch", False),
        ("生成式 AI 工程实践", "torch", False),
        ("模型部署与服务化", "engineering", False),
        ("并行计算与性能优化", "engineering", False),
        ("AI 安全与可靠性", "engineering", False),
        ("智能体系统设计", "torch", False),
        ("综合 AI 项目工作坊", "torch", False),
    ],
}


DOMAIN_ENVIRONMENT = {
    "python": "basic",
    "algorithm": "basic",
    "engineering": "basic",
    "data": "data",
    "ml": "data",
    "torch": "torch-cpu",
}


DOMAIN_TOPICS = {
    "python": [
        "变量、类型与表达式",
        "函数、模块与异常处理",
        "面向对象与可复用设计",
        "文件、网络与数据接口",
        "测试驱动与代码重构",
        "综合项目与工程交付",
    ],
    "algorithm": [
        "复杂度分析与递归",
        "线性表、栈、队列与哈希",
        "树、堆与优先队列",
        "排序、查找与双指针",
        "图搜索与最短路径",
        "动态规划与综合优化",
    ],
    "engineering": [
        "需求拆解与接口设计",
        "模块化、异常与日志",
        "数据校验与安全边界",
        "自动化测试与持续集成",
        "性能分析与可观测性",
        "发布、回滚与故障演练",
    ],
    "data": [
        "数据读取、清洗与质量检查",
        "数组运算与向量化思维",
        "表格变换、连接与聚合",
        "统计描述与可视化表达",
        "特征构造与数据管道",
        "分析报告与业务结论",
    ],
    "ml": [
        "监督学习问题建模",
        "线性模型与正则化",
        "树模型与集成方法",
        "训练验证与交叉验证",
        "指标选择与误差分析",
        "模型解释与上线评估",
    ],
    "torch": [
        "Tensor、设备与批处理",
        "自动求导与优化器",
        "神经网络模块与损失函数",
        "数据集、训练循环与验证",
        "模型保存、加载与推理",
        "实验记录与性能复盘",
    ],
}


EXPERIMENT_SPECS = [
    {
        "name": "基础环境：函数与单元测试",
        "slug": "basic",
        "imports": ["pytest"],
        "objective": "编写一个可测试的统计函数，并使用 pytest 验证边界条件。",
        "setup": "import pytest\n\ndef assert_close(actual, expected):\n    assert actual == expected",
        "exercise": "def average(values):\n    \"\"\"返回非空数值列表的平均值。\"\"\"\n    pass\n\nprint(average([1, 2, 3, 4]))",
        "expected": "2.5",
    },
    {
        "name": "基础环境：列表与字典",
        "slug": "basic",
        "imports": [],
        "objective": "使用列表、字典和集合完成成绩汇总，关注空输入与重复数据。",
        "setup": "scores = [{\"name\": \"A\", \"score\": 88}, {\"name\": \"B\", \"score\": 92}]",
        "exercise": "def top_student(scores):\n    pass\n\nprint(top_student(scores))",
        "expected": "B",
    },
    {
        "name": "基础环境：排序与查找",
        "slug": "basic",
        "imports": [],
        "objective": "实现二分查找，并通过有序、空列表和重复值场景验证算法。",
        "setup": "items = [2, 4, 7, 11, 18, 25]",
        "exercise": "def binary_search(items, target):\n    pass\n\nprint(binary_search(items, 11))",
        "expected": "3",
    },
    {
        "name": "基础环境：pytest 边界测试",
        "slug": "basic",
        "imports": ["pytest"],
        "objective": "为字符串规范化函数补充参数化测试，理解测试夹具和断言。",
        "setup": "cases = [(\" Hello \", \"hello\"), (\"WORLD\", \"world\"), (\"\", \"\")]",
        "exercise": "def normalize_text(value):\n    pass\n\nfor raw, expected in cases:\n    print(normalize_text(raw) == expected)",
        "expected": "True\nTrue\nTrue",
    },
    {
        "name": "数据环境：NumPy 向量化",
        "slug": "data",
        "imports": ["numpy"],
        "objective": "使用 NumPy 完成向量化标准化，比较循环写法与数组写法。",
        "setup": "import numpy as np\nvalues = np.array([10.0, 20.0, 30.0, 40.0])",
        "exercise": "def zscore(values):\n    import numpy as np\n    pass\n\nprint(zscore(values))",
        "expected": "[-1.3416 -0.4472 0.4472 1.3416]",
    },
    {
        "name": "数据环境：Pandas 数据清洗",
        "slug": "data",
        "imports": ["numpy", "pandas"],
        "objective": "使用 Pandas 处理缺失值、重复记录和分组统计。",
        "setup": "import pandas as pd\nimport numpy as np\ndf = pd.DataFrame({\"team\": [\"A\", \"A\", \"B\"], \"score\": [80, np.nan, 90]})",
        "exercise": "def clean_scores(df):\n    pass\n\nprint(clean_scores(df).to_dict(orient=\"records\"))",
        "expected": "缺失分数被组内均值填充",
    },
    {
        "name": "数据环境：SciPy 统计检验",
        "slug": "data",
        "imports": ["numpy", "scipy"],
        "objective": "使用 SciPy 计算描述统计量，并解释样本差异与置信水平。",
        "setup": "import numpy as np\nfrom scipy import stats\nsample = np.array([10, 11, 10, 12, 9, 11])",
        "exercise": "from scipy import stats\nprint(stats.describe(sample).nobs)\nprint(round(float(sample.mean()), 2))",
        "expected": "6\n10.5",
    },
    {
        "name": "数据环境：Scikit-learn 特征管道",
        "slug": "data",
        "imports": ["numpy", "sklearn"],
        "objective": "构造训练验证划分和标准化管道，观察数据泄漏对评估的影响。",
        "setup": "import numpy as np\nfrom sklearn.model_selection import train_test_split\nX = np.array([[1], [2], [3], [4], [5], [6]])\ny = np.array([0, 0, 0, 1, 1, 1])",
        "exercise": "from sklearn.pipeline import make_pipeline\nfrom sklearn.preprocessing import StandardScaler\nprint(make_pipeline(StandardScaler()).steps[0][0])",
        "expected": "standardscaler",
    },
    {
        "name": "Torch 环境：Tensor 基础",
        "slug": "torch-cpu",
        "imports": ["torch"],
        "objective": "创建 Tensor、执行广播和归约操作，理解 CPU Tensor 的形状规则。",
        "setup": "import torch\nx = torch.tensor([[1.0, 2.0], [3.0, 4.0]])",
        "exercise": "def row_sum(x):\n    import torch\n    return x.sum(dim=1)\n\nprint(row_sum(x))",
        "expected": "tensor([3., 7.])",
    },
    {
        "name": "Torch 环境：自动求导",
        "slug": "torch-cpu",
        "imports": ["torch"],
        "objective": "观察标量函数的梯度，理解 requires_grad 和 backward 的关系。",
        "setup": "import torch\nw = torch.tensor(2.0, requires_grad=True)",
        "exercise": "loss = (w - 5) ** 2\nloss.backward()\nprint(float(w.grad))",
        "expected": "-6.0",
    },
    {
        "name": "Torch 环境：线性回归训练",
        "slug": "torch-cpu",
        "imports": ["torch"],
        "objective": "实现一个小型线性回归训练循环，记录损失下降过程。",
        "setup": "import torch\nx = torch.tensor([[1.0], [2.0], [3.0]])\ny = torch.tensor([[2.0], [4.0], [6.0]])",
        "exercise": "model = torch.nn.Linear(1, 1)\noptimizer = torch.optim.SGD(model.parameters(), lr=0.05)\nprint(sum(p.numel() for p in model.parameters()))",
        "expected": "2",
    },
    {
        "name": "Torch 环境：训练与验证",
        "slug": "torch-cpu",
        "imports": ["torch"],
        "objective": "将数据划分为训练集和验证集，比较训练指标与验证指标。",
        "setup": "import torch\nfeatures = torch.arange(0, 8, dtype=torch.float32).reshape(-1, 1)",
        "exercise": "train, validation = features[:6], features[6:]\nprint(train.shape, validation.shape)",
        "expected": "torch.Size([6, 1]) torch.Size([2, 1])",
    },
]


BASIC_TASKS = [
    {
        "title": "正数求和",
        "function_name": "sum_positive",
        "signature": "def sum_positive(values: list[int]) -> int:",
        "description": "返回列表中所有正数的和；空列表返回 0。",
        "starter": "def sum_positive(values):\n    pass",
        "cases": [{"args": [[-2, 3, 4]], "expected": 7}, {"args": [[]], "expected": 0}],
        "hidden": """import user_code

def test_positive_and_negative():
    assert user_code.sum_positive([-2, 3, 4]) == 7

def test_empty():
    assert user_code.sum_positive([]) == 0

def test_all_negative():
    assert user_code.sum_positive([-5, -1]) == 0
""",
        "solution": "def sum_positive(values):\n    return sum(v for v in values if v > 0)",
    },
    {
        "title": "括号匹配",
        "function_name": "is_balanced",
        "signature": "def is_balanced(text: str) -> bool:",
        "description": "判断字符串中的圆括号、方括号和花括号是否正确嵌套。",
        "starter": "def is_balanced(text):\n    pass",
        "cases": [{"args": ["([])"], "expected": True}, {"args": ["([)]"], "expected": False}],
        "hidden": """import user_code

def test_nested():
    assert user_code.is_balanced("{[()]}") is True

def test_mismatch():
    assert user_code.is_balanced("([)]") is False

def test_empty():
    assert user_code.is_balanced("") is True
""",
        "solution": "def is_balanced(text):\n    pairs = {')': '(', ']': '[', '}': '{'}\n    stack = []\n    for char in text:\n        if char in '([{':\n            stack.append(char)\n        elif char in pairs and (not stack or stack.pop() != pairs[char]):\n            return False\n    return not stack",
    },
    {
        "title": "二分查找",
        "function_name": "binary_search",
        "signature": "def binary_search(values: list[int], target: int) -> int:",
        "description": "在升序整数列表中查找目标值，返回下标；不存在时返回 -1。",
        "starter": "def binary_search(values, target):\n    pass",
        "cases": [{"args": [[1, 3, 5, 7], 5], "expected": 2}, {"args": [[], 1], "expected": -1}],
        "hidden": """import user_code

def test_found():
    assert user_code.binary_search([1, 3, 5, 7], 5) == 2

def test_missing():
    assert user_code.binary_search([1, 3, 5, 7], 6) == -1

def test_empty():
    assert user_code.binary_search([], 1) == -1
""",
        "solution": "def binary_search(values, target):\n    left, right = 0, len(values) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if values[mid] == target:\n            return mid\n        if values[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1",
    },
]


DATA_TASKS = [
    {
        "title": "向量标准化",
        "function_name": "zscore",
        "signature": "def zscore(values: list[float]) -> list[float]:",
        "description": "使用 NumPy 返回均值为 0、标准差为 1 的标准化向量。",
        "starter": "def zscore(values):\n    import numpy as np\n    pass",
        "cases": [{"args": [[1.0, 2.0, 3.0]], "expected": [-1.2247, 0.0, 1.2247]}],
        "hidden": """import numpy as np
import user_code

def test_zscore():
    result = np.array(user_code.zscore([1.0, 2.0, 3.0]))
    assert np.allclose(result, [-1.22474487, 0.0, 1.22474487])
""",
        "solution": "def zscore(values):\n    import numpy as np\n    array = np.asarray(values, dtype=float)\n    return ((array - array.mean()) / array.std()).tolist()",
    },
    {
        "title": "填充缺失成绩",
        "function_name": "fill_missing_scores",
        "signature": "def fill_missing_scores(values: list[float | None]) -> list[float]:",
        "description": "使用 Pandas 以非缺失成绩均值填充缺失值。",
        "starter": "def fill_missing_scores(values):\n    import pandas as pd\n    pass",
        "cases": [{"args": [[80, None, 100]], "expected": [80.0, 90.0, 100.0]}],
        "hidden": """import pandas as pd
import user_code

def test_fill_mean():
    result = user_code.fill_missing_scores([80, None, 100])
    assert result == [80.0, 90.0, 100.0]

def test_no_missing():
    assert user_code.fill_missing_scores([1, 2]) == [1.0, 2.0]
""",
        "solution": "def fill_missing_scores(values):\n    import pandas as pd\n    return pd.Series(values, dtype='float64').fillna(pd.Series(values, dtype='float64').mean()).tolist()",
    },
    {
        "title": "线性拟合预测",
        "function_name": "predict_linear",
        "signature": "def predict_linear(x: list[float], y: list[float], target: float) -> float:",
        "description": "使用 NumPy 对样本进行一次线性拟合，并预测目标 x 的 y 值。",
        "starter": "def predict_linear(x, y, target):\n    import numpy as np\n    pass",
        "cases": [{"args": [[1, 2, 3], [2, 4, 6], 4], "expected": 8.0}],
        "hidden": """import numpy as np
import user_code

def test_line():
    assert np.isclose(user_code.predict_linear([1, 2, 3], [2, 4, 6], 4), 8.0)
""",
        "solution": "def predict_linear(x, y, target):\n    import numpy as np\n    slope, intercept = np.polyfit(np.asarray(x), np.asarray(y), 1)\n    return float(slope * target + intercept)",
    },
]


TORCH_TASKS = [
    {
        "title": "Tensor 行求和",
        "function_name": "tensor_row_sum",
        "signature": "def tensor_row_sum(values: list[list[float]]) -> list[float]:",
        "description": "使用 PyTorch 返回二维数据每一行的和。",
        "starter": "def tensor_row_sum(values):\n    import torch\n    pass",
        "cases": [{"args": [[[1, 2], [3, 4]]], "expected": [3.0, 7.0]}],
        "hidden": """import torch
import user_code

def test_row_sum():
    result = user_code.tensor_row_sum([[1, 2], [3, 4]])
    assert torch.allclose(torch.tensor(result), torch.tensor([3.0, 7.0]))
""",
        "solution": "def tensor_row_sum(values):\n    import torch\n    return torch.tensor(values, dtype=torch.float32).sum(dim=1).tolist()",
    },
    {
        "title": "线性层前向计算",
        "function_name": "linear_forward",
        "signature": "def linear_forward(values: list[float], weights: list[float], bias: float) -> list[float]:",
        "description": "使用 PyTorch 完成一维线性层的前向计算。",
        "starter": "def linear_forward(values, weights, bias):\n    import torch\n    pass",
        "cases": [{"args": [[1, 2], [2, 3], 1], "expected": [3.0, 7.0]}],
        "hidden": """import torch
import user_code

def test_forward():
    result = user_code.linear_forward([1, 2], [2, 3], 1)
    assert torch.allclose(torch.tensor(result), torch.tensor([3.0, 7.0]))
""",
        "solution": "def linear_forward(values, weights, bias):\n    import torch\n    x = torch.tensor(values, dtype=torch.float32)\n    w = torch.tensor(weights, dtype=torch.float32)\n    return (x * w + bias).tolist()",
    },
    {
        "title": "单步梯度更新",
        "function_name": "gradient_step",
        "signature": "def gradient_step(weight: float, target: float, learning_rate: float) -> float:",
        "description": "对平方损失执行一步梯度下降，返回更新后的权重。",
        "starter": "def gradient_step(weight, target, learning_rate):\n    import torch\n    pass",
        "cases": [{"args": [1.0, 3.0, 0.1], "expected": 1.4}],
        "hidden": """import torch
import user_code

def test_update():
    assert abs(user_code.gradient_step(1.0, 3.0, 0.1) - 1.4) < 1e-6
""",
        "solution": "def gradient_step(weight, target, learning_rate):\n    import torch\n    w = torch.tensor(float(weight), requires_grad=True)\n    loss = (w - float(target)) ** 2\n    loss.backward()\n    return float(w - learning_rate * w.grad)",
    },
]


def _password(name: str, default: str = DEFAULT_PASSWORD) -> str:
    """读取内测账号密码；变量名采用项目已有的 DAI_* 配置风格。"""
    import os

    return os.getenv(name, default)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _cover_url(index: int) -> str:
    return f"https://placehold.co/1200x675/png?text=DAI+Course+{index:02d}"


def _video_url(course_index: int, chapter_index: int) -> str:
    return f"https://example.com/dai-course-videos/course-{course_index:02d}/chapter-{chapter_index:02d}"


def _lesson_markdown(course_title: str, topic: str, lesson_kind: str) -> str:
    return (
        f"# {topic}\n\n"
        f"本课时属于《{course_title}》的{lesson_kind}，目标是把概念、代码和验证过程串成一个可复用的学习闭环。\n\n"
        "## 学习目标\n"
        f"- 理解 **{topic}** 的核心概念、适用条件和常见误区；\n"
        "- 能够用 Python 写出结构清晰、可测试的示例；\n"
        "- 能够通过输入输出、边界条件和复杂度分析检查实现质量。\n\n"
        "## 教学内容\n"
        "先从一个最小问题开始，再逐步引入数据约束和工程约束。编写代码时请保留函数边界，"
        "给关键分支添加注释，并使用至少一个正常场景、一个边界场景进行验证。课堂讨论重点包括："
        "为什么这样建模、替代方案的代价是什么，以及如何在实验报告中用证据支持结论。\n\n"
        "## 课后练习\n"
        "完成课时末尾的练习，提交运行结果和一段不少于 100 字的反思，说明你发现的一个问题、"
        "定位过程以及下一步改进方案。"
    )


def _environment_map(db: Session) -> dict[str, EnvironmentVersion]:
    """在任何清理动作前解析三类可运行环境。"""
    try:
        versions = db.scalars(
            select(EnvironmentVersion)
            .join(EnvironmentProfile, EnvironmentProfile.id == EnvironmentVersion.profile_id)
            .where(
                EnvironmentProfile.slug.in_(ENVIRONMENT_SLUGS),
                EnvironmentProfile.status == "active",
                EnvironmentVersion.status == "available",
                EnvironmentVersion.image_digest.is_not(None),
            )
            .order_by(EnvironmentProfile.slug, EnvironmentVersion.version_number.desc())
        ).all()
    except SQLAlchemyError as exc:
        raise RuntimeError("环境控制面尚未完成迁移，请先部署 environment_profiles 等表") from exc

    result: dict[str, EnvironmentVersion] = {}
    for version in versions:
        profile = db.get(EnvironmentProfile, version.profile_id)
        if profile and profile.slug not in result:
            result[profile.slug] = version

    missing = [slug for slug in ENVIRONMENT_SLUGS if slug not in result]
    if missing:
        raise RuntimeError(
            "以下环境没有可用且带 image_digest 的版本："
            + ", ".join(missing)
            + "。请先运行 seed-environments --enqueue 并等待构建完成。"
        )
    return result


def _clear_business_data(db: Session) -> None:
    """清理业务数据，保留环境控制面和 admin。

    Notebook 模板存在 current_version_id 循环外键，所以删除前先断开该引用；
    环境控制面中的 created_by/updated_by 仅在指向即将删除的业务账号时置空，
    不触碰环境版本、镜像 digest 或构建状态。
    """
    tables = Base.metadata.tables
    template_table = tables.get("notebook_templates")
    version_table = tables.get("notebook_template_versions")
    if template_table is not None:
        db.execute(update(template_table).values(current_version_id=None))
        db.flush()

    # 先按外键拓扑逆序清理所有业务表，保留环境控制面和模板循环表。
    skipped = PRESERVED_TABLES | {"users", "notebook_templates", "notebook_template_versions"}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in skipped:
            db.execute(delete(table))

    if version_table is not None:
        db.execute(delete(version_table))
    if template_table is not None:
        db.execute(delete(template_table))

    removed_ids = list(db.scalars(select(User.id).where(User.username != "admin")).all())
    if removed_ids:
        for table_name in PRESERVED_TABLES:
            table = tables.get(table_name)
            if table is None:
                continue
            for column_name in ("created_by_id", "updated_by_id"):
                column = table.c.get(column_name)
                if column is not None:
                    db.execute(
                        update(table).where(column.in_(removed_ids)).values({column_name: None})
                    )
        db.execute(delete(User).where(User.id.in_(removed_ids)))
    db.flush()


def _unique_student_names(count: int) -> list[str]:
    rng = random.Random(SEED_RANDOM_SEED)
    surnames = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪解应宗丁宣邓单杭洪包诸左石崔吉钮龚程邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公万俟司马上官欧阳夏侯诸葛闻人东方赫连皇甫尉迟公羊澹台公冶宗政濮阳淳于单于太叔申屠公孙仲孙轩辕令狐钟离宇文长孙慕容鲜于闾丘司徒司空亓官司寇仉督子车颛孙端木巫马公西漆雕乐正壤驷公良拓跋夹谷宰父谷梁晋楚闫法汝鄢涂钦段干百里东郭南门呼延归海羊舌微生岳帅缑亢况后有琴梁丘左丘东门西门商牟佘佴伯赏南宫墨哈谯笪年爱阳佟第五言福")
    given = list("伟芳娜秀英敏静丽强磊军洋勇艳杰娟涛明超秀兰霞平刚桂英华慧巧美娜健峰文鹏飞鑫玲琳丹倩雪宁婷欢宇浩然子涵梓轩雨桐思远清禾明远知行若安嘉言景行书瑶沐阳星河芷晴安然可欣亦凡向晨语嫣昊天心怡博文佳宁晨曦逸凡念慈舒雅承泽锦程乐言予安一诺")
    names: list[str] = []
    used: set[str] = set()
    while len(names) < count:
        name = rng.choice(surnames) + rng.choice(given)
        if name not in used:
            used.add(name)
            names.append(name)
    return names


def _create_users(db: Session) -> dict[str, Any]:
    admin_password = _password("DAI_SEED_ADMIN_PASSWORD")
    teacher_password = _password("DAI_SEED_TEACHER_PASSWORD")
    student_password = _password("DAI_SEED_STUDENT_PASSWORD")
    developer_password = _password("DAI_SEED_DEVELOPER_PASSWORD")
    # 同一角色的内测账号共享密码；每类密码只做一次 bcrypt，避免 400 名学生
    # 让一次种子执行变成数分钟的 CPU 密集任务。
    admin_hash = hash_password(admin_password)
    teacher_hash = hash_password(teacher_password)
    student_hash = hash_password(student_password)
    developer_hash = hash_password(developer_password)

    admin = db.scalar(select(User).where(User.username == "admin"))
    if admin is None:
        admin = User(
            username="admin",
            password_hash=admin_hash,
            real_name="系统管理员",
            role="admin",
            status="active",
        )
        db.add(admin)
    else:
        admin.password_hash = admin_hash
        admin.real_name = "系统管理员"
        admin.role = "admin"
        admin.status = "active"
    db.flush()

    users: dict[str, Any] = {"admin": admin}
    for username, real_name, role in TEACHER_DEFS:
        user = User(
            username=username,
            password_hash=teacher_hash,
            real_name=real_name,
            role=role,
            status="active",
        )
        db.add(user)
        db.flush()
        users[username] = user

    developer = User(
        username="developer_lab",
        password_hash=developer_hash,
        real_name="实验平台开发者",
        role="developer",
        status="active",
    )
    db.add(developer)
    db.flush()
    users["developer_lab"] = developer

    students: list[User] = []
    names = _unique_student_names(400)
    name_index = 0
    for class_index, prefix in enumerate(CLASS_PREFIXES):
        for student_index in range(1, 41):
            username = f"student_{prefix}_{student_index:02d}"
            student = User(
                username=username,
                student_no=f"{prefix}{student_index:02d}",
                password_hash=student_hash,
                real_name=names[name_index],
                role="student",
                status="active",
            )
            name_index += 1
            db.add(student)
            students.append(student)
        db.flush()
    users["students"] = students
    return users


def _create_academics(db: Session, users: dict[str, Any], anchor: datetime) -> dict[str, Any]:
    term = AcademicTerm(
        code="2026-INTERNAL-TEST",
        name="2026 生产前内测学期",
        start_date=anchor.date() - timedelta(days=30),
        end_date=anchor.date() + timedelta(days=150),
        status="active",
    )
    db.add(term)
    db.flush()

    classes: list[TeachingClass] = []
    students: list[User] = users["students"]
    for class_index, prefix in enumerate(CLASS_PREFIXES):
        teaching_class = TeachingClass(
            academic_term_id=term.id,
            code=f"DAI-{2601 + class_index}",
            name=f"DAI 智能实验班 {class_index + 1:02d}",
            status="active",
        )
        db.add(teaching_class)
        db.flush()
        class_students = students[class_index * 40 : (class_index + 1) * 40]
        db.add_all(
            [
                TeachingClassStudent(
                    teaching_class_id=teaching_class.id,
                    student_id=student.id,
                    status="active",
                )
                for student in class_students
            ]
        )
        classes.append(teaching_class)
    db.flush()
    return {"term": term, "classes": classes}


def _experiment_cells(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "intro",
            "type": "markdown",
            "source": f"# {spec['name']}\n\n{spec['objective']}\n\n预期输出：{spec['expected']}",
            "order": 0,
            "student_editable": False,
            "source_hidden": False,
        },
        {
            "id": "setup",
            "type": "code",
            "source": spec["setup"],
            "order": 1,
            "student_editable": False,
            "source_hidden": True,
        },
        {
            "id": "exercise",
            "type": "code",
            "source": spec["exercise"],
            "order": 2,
            "student_editable": True,
            "source_hidden": False,
        },
        {
            "id": "reflection",
            "type": "markdown",
            "source": "## 实验报告\n记录一次运行结果、一个边界条件和一个你认为值得改进的实现细节。",
            "order": 3,
            "student_editable": False,
            "source_hidden": False,
        },
    ]


def _create_experiments(
    db: Session,
    users: dict[str, Any],
    environments: dict[str, EnvironmentVersion],
) -> dict[str, Any]:
    templates_by_env: dict[str, list[tuple[NotebookTemplate, NotebookTemplateVersion]]] = {
        slug: [] for slug in ENVIRONMENT_SLUGS
    }
    modules: list[ExperimentModule] = []
    for index, spec in enumerate(EXPERIMENT_SPECS):
        env = environments[spec["slug"]]
        cells = _experiment_cells(spec)
        cell_order = [cell["id"] for cell in cells]
        digest = hashlib.sha256(
            json.dumps(cells, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        template = NotebookTemplate(
            name=spec["name"],
            description=spec["objective"],
            status="published",
            owner_id=users["teacher_zhang"].id,
            draft_cells=cells,
            draft_revision=1,
            draft_metadata={"seed": True, "environment": spec["slug"]},
            draft_assets_dir=None,
            draft_environment_version_id=env.id,
            draft_import_policy_mode="restricted",
            draft_allowed_imports=spec["imports"],
        )
        db.add(template)
        db.flush()
        version = NotebookTemplateVersion(
            template_id=template.id,
            version_number=1,
            sha256=digest,
            cells=cells,
            cell_order=cell_order,
            notebook_metadata={"seed": True, "environment": spec["slug"]},
            assets_dir=None,
            published_by_id=users["teacher_zhang"].id,
            environment_version_id=env.id,
            import_policy_mode="restricted",
            allowed_imports=spec["imports"],
        )
        db.add(version)
        db.flush()
        template.current_version_id = version.id
        db.flush()

        module = ExperimentModule(
            name=spec["name"],
            description=spec["objective"],
            template_id=template.id,
            owner_id=users["teacher_zhang"].id,
            status="published",
        )
        db.add(module)
        db.flush()
        templates_by_env[spec["slug"]].append((template, version))
        modules.append(module)

    return {"templates_by_env": templates_by_env, "modules": modules}


def _course_class_indices(course_index: int, typical: bool) -> list[int]:
    if typical:
        return list(range(10))
    first = (course_index * 2) % 10
    return sorted({first, (first + 1) % 10, (first + 5) % 10})


def _create_courses(
    db: Session,
    users: dict[str, Any],
    academics: dict[str, Any],
    experiments: dict[str, Any],
    anchor: datetime,
) -> tuple[dict[str, dict[str, Any]], list[tuple[Lesson, NotebookTemplateVersion]]]:
    courses: dict[str, dict[str, Any]] = {}
    notebook_lessons: list[tuple[Lesson, NotebookTemplateVersion]] = []
    course_index = 0
    for teacher_key, specs in COURSE_CATALOG.items():
        for title, domain, typical in specs:
            course_index += 1
            course = Course(
                title=title,
                description=(
                    f"本课程面向生产前教学与实验，围绕{DOMAIN_TOPICS[domain][0]}、"
                    f"{DOMAIN_TOPICS[domain][1]}和{DOMAIN_TOPICS[domain][2]}组织理论、代码、"
                    "实验和评价活动，帮助学生形成可复现、可解释、可交付的实践能力。"
                ),
                status="published",
                teacher_id=users[teacher_key].id,
                academic_term_id=academics["term"].id,
                cover=_cover_url(course_index),
                start_time=anchor - timedelta(days=21),
                visibility="class",
                default_score=100.0,
            )
            db.add(course)
            db.flush()

            class_indices = _course_class_indices(course_index - 1, typical)
            for class_index in class_indices:
                db.add(
                    CourseTeachingClass(
                        course_id=course.id,
                        teaching_class_id=academics["classes"][class_index].id,
                    )
                )
            db.flush()

            topics = DOMAIN_TOPICS[domain][: 6 if typical else 3]
            environment_slug = DOMAIN_ENVIRONMENT[domain]
            templates = experiments["templates_by_env"][environment_slug]
            for chapter_index, topic in enumerate(topics):
                chapter = Chapter(
                    course_id=course.id,
                    title=f"第{chapter_index + 1}章 {topic}",
                    order_index=chapter_index,
                )
                db.add(chapter)
                db.flush()
                lesson_specs = [
                    ("概念导读", "markdown"),
                    ("课堂讲解", "video"),
                    ("动手实验", "notebook"),
                    ("练习与复盘", "markdown"),
                ]
                for lesson_index, (suffix, content_type) in enumerate(lesson_specs):
                    template, version = templates[chapter_index % len(templates)]
                    lesson = Lesson(
                        chapter_id=chapter.id,
                        title=f"{topic}：{suffix}",
                        content_type=content_type,
                        content=_lesson_markdown(title, topic, suffix),
                        template_id=template.id if content_type == "notebook" else None,
                        video_url=(
                            _video_url(course_index, chapter_index + 1)
                            if content_type == "video"
                            else None
                        ),
                        order_index=lesson_index,
                        status="published",
                    )
                    db.add(lesson)
                    db.flush()
                    if content_type == "notebook":
                        notebook_lessons.append((lesson, version))

            courses[title] = {
                "course": course,
                "teacher_key": teacher_key,
                "domain": domain,
                "typical": typical,
                "class_indices": class_indices,
            }
    db.flush()
    return courses, notebook_lessons


def _create_enrollments(db: Session, academics: dict[str, Any], courses: dict[str, dict[str, Any]], users: dict[str, Any]) -> None:
    students: list[User] = users["students"]
    classes = academics["classes"]
    for item in courses.values():
        for class_index in item["class_indices"]:
            class_students = students[class_index * 40 : (class_index + 1) * 40]
            db.add_all(
                [
                    CourseEnrollment(
                        course_id=item["course"].id,
                        student_id=student.id,
                        status="enrolled",
                        origin="class",
                    )
                    for student in class_students
                ]
            )
    db.flush()


def _task_for_environment(slug: str, index: int) -> dict[str, Any]:
    tasks = {"basic": BASIC_TASKS, "data": DATA_TASKS, "torch-cpu": TORCH_TASKS}[slug]
    return tasks[index % len(tasks)]


AI_DEMO_ASSIGNMENT_SPECS = (
    {
        "title": f"{TYPICAL_COURSE_TITLE}｜AI评分演示作业一｜正数求和",
        "description": "AI 评分演示：在 basic 环境中实现正数求和，系统会结合功能测试、边界测试和代码质量进行评分。",
        "environment": "basic",
        "task": BASIC_TASKS[0],
        "due_offset": 2,
    },
    {
        "title": f"{TYPICAL_COURSE_TITLE}｜AI评分演示作业二｜缺失成绩填充",
        "description": "AI 评分演示：在 data 环境中使用 Pandas 填充缺失成绩，关注空值处理、平均值计算和可读性。",
        "environment": "data",
        "task": DATA_TASKS[1],
        "due_offset": 5,
    },
    {
        "title": f"{TYPICAL_COURSE_TITLE}｜AI评分演示作业三｜Tensor 行求和",
        "description": "AI 评分演示：在 torch-cpu 环境中使用 PyTorch 完成二维 Tensor 行求和，关注张量类型与形状。",
        "environment": "torch-cpu",
        "task": TORCH_TASKS[0],
        "due_offset": 8,
    },
)


AI_DEMO_EXAM_SPECS = (
    {
        "title": f"{TYPICAL_COURSE_TITLE}｜AI评分演示考试一｜Python 函数理解",
        "environment": "basic",
        "task": BASIC_TASKS[1],
        "choice_prompt": "使用栈判断括号是否匹配时，遇到右括号最应该先检查什么？",
        "choice_options": {
            "A": "字符串长度是否为偶数",
            "B": "栈是否为空以及栈顶是否匹配",
            "C": "所有字符是否都是 ASCII",
            "D": "是否已经遍历到字符串末尾",
        },
        "choice_answer": ["B"],
        "start_offset": -7,
        "end_offset": 30,
    },
    {
        "title": f"{TYPICAL_COURSE_TITLE}｜AI评分演示考试二｜数据处理函数",
        "environment": "data",
        "task": DATA_TASKS[2],
        "choice_prompt": "使用 NumPy 进行线性拟合预测时，最重要的输入关系是什么？",
        "choice_options": {
            "A": "训练样本中的 x 与 y 一一对应",
            "B": "所有 y 都必须相同",
            "C": "target 必须出现在训练样本中",
            "D": "样本数量必须是偶数",
        },
        "choice_answer": ["A"],
        "start_offset": -2,
        "end_offset": 45,
    },
    {
        "title": f"{TYPICAL_COURSE_TITLE}｜AI评分演示考试三｜PyTorch 梯度更新",
        "environment": "torch-cpu",
        "task": TORCH_TASKS[2],
        "choice_prompt": "在 PyTorch 自动求导中，调用 loss.backward() 的直接作用是什么？",
        "choice_options": {
            "A": "清空模型参数",
            "B": "把 Tensor 转成 NumPy 数组",
            "C": "计算参与计算图的参数梯度",
            "D": "自动执行 optimizer.step()",
        },
        "choice_answer": ["C"],
        "start_offset": -1,
        "end_offset": 60,
    },
)


AI_DEMO_ROBUSTNESS_TESTS = {
    "sum_positive": """def test_robustness():
    assert sum_positive([]) == 0
    assert sum_positive([-3, 0, 2, 5]) == 7
""",
    "is_balanced": """def test_robustness():
    assert is_balanced("") is True
    assert is_balanced("(") is False
    assert is_balanced("([{}])") is True
    assert is_balanced("(]") is False
""",
    "binary_search": """def test_robustness():
    assert binary_search([], 1) == -1
    assert binary_search([1, 2, 2, 3], 2) in (1, 2)
    assert binary_search([1, 2, 3], 9) == -1
""",
    "fill_missing_scores": """def test_robustness():
    assert fill_missing_scores([80, None, 100]) == [80.0, 90.0, 100.0]
    assert fill_missing_scores([1, 2]) == [1.0, 2.0]
""",
    "predict_linear": """def test_robustness():
    assert abs(predict_linear([0, 1], [1, 3], 2) - 5.0) < 1e-6
""",
    "zscore": """def test_robustness():
    result = zscore([1.0, 2.0, 3.0])
    assert len(result) == 3
    assert abs(sum(result)) < 1e-6
""",
    "tensor_row_sum": """def test_robustness():
    assert tensor_row_sum([[0, 0], [2, 3]]) == [0.0, 5.0]
""",
    "linear_forward": """def test_robustness():
    assert linear_forward([0, 2], [3, 4], 1) == [1.0, 9.0]
""",
    "gradient_step": """def test_robustness():
    result = gradient_step(1.0, 3.0, 0.1)
    assert abs(result - 1.4) < 1e-6
""",
}


def _allowed_imports_for_environment(slug: str) -> list[str]:
    if slug == "basic":
        return ["pytest"]
    if slug == "data":
        return ["numpy", "pandas", "scipy", "sklearn", "matplotlib"]
    return ["torch"]


def _ai_test_groups(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "F1",
            "name": "功能正确性",
            "dimension": "F",
            "max_score": 60,
            "tests": task["hidden"],
        },
        {
            "id": "R1",
            "name": "鲁棒性与边界",
            "dimension": "R",
            "max_score": 10,
            "tests": AI_DEMO_ROBUSTNESS_TESTS.get(
                task["function_name"], "def test_robustness():\n    assert True\n"
            ),
        },
    ]


def _ai_rubric_document(task: dict[str, Any], *, is_exam: bool) -> dict[str, Any]:
    return {
        "rubric_version": 1,
        "question_type": "考试编程题" if is_exam else "课程作业编程题",
        "learning_objective": task["description"],
        "explicit_requirements": [
            f"实现 {task['function_name']} 函数并保持题目给出的函数签名",
            "通过公开样例和隐藏测试，正确处理正常输入与边界输入",
        ],
        "teacher_constraints": [
            "不得修改评测入口或绕过测试",
            "优先使用清晰、可维护且与题目环境匹配的实现",
        ],
        "accepted_strategies": [
            "允许使用等价的算法实现，只要输入输出契约和边界行为一致",
            "允许合理的辅助变量、辅助函数和标准库/题目环境白名单内的包",
        ],
        "algorithm_criteria": [
            {"id": "A1", "name": "核心功能实现", "points": 10, "description": "正常输入下得到正确结果"},
            {"id": "A2", "name": "算法思路与实现", "points": 6, "description": "实现逻辑与数据处理过程合理"},
            {"id": "A3", "name": "边界处理与复杂度", "points": 4, "description": "覆盖边界情况并避免明显低效实现"},
        ],
        "quality_criteria": [
            {"id": "Q1", "name": "可读性与命名", "points": 3, "description": "命名清晰，代码易于理解"},
            {"id": "Q2", "name": "代码结构", "points": 3, "description": "结构清晰，职责合理"},
            {"id": "Q3", "name": "重复与冗余", "points": 2, "description": "没有明显重复或无效代码"},
            {"id": "Q4", "name": "接口、规范与安全", "points": 2, "description": "遵守函数接口和运行环境约束"},
        ],
        "uncertain_items": [],
    }


def _ensure_seed_rubric(
    db: Session,
    question: JudgeQuestion | ExamQuestion,
    task: dict[str, Any],
    *,
    is_exam: bool,
    anchor: datetime,
) -> QuestionRubric:
    target_column = QuestionRubric.exam_question_id if is_exam else QuestionRubric.judge_question_id
    existing = db.scalars(
        select(QuestionRubric)
        .where(target_column == question.id, QuestionRubric.status == "locked")
        .order_by(QuestionRubric.version.desc())
        .limit(1)
    ).first()
    if existing is not None:
        return existing

    rubric_json = _ai_rubric_document(task, is_exam=is_exam)
    snapshot = {
        "title": getattr(question, "title", None) or getattr(question, "prompt", ""),
        "description": getattr(question, "description", None) or task["description"],
        "function_name": task["function_name"],
        "is_exam": is_exam,
        "teacher_constraints": question.teacher_constraints or {},
        "test_groups": question.test_groups or [],
        "reference_solution": task["solution"],
    }
    hash_snapshot = {key: value for key, value in snapshot.items() if key != "reference_solution"}
    source_hash = hashlib.sha256(
        json.dumps(hash_snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    max_version = db.scalar(
        select(func.max(QuestionRubric.version)).where(target_column == question.id)
    ) or 0
    rubric = QuestionRubric(
        exam_question_id=question.id if is_exam else None,
        judge_question_id=None if is_exam else question.id,
        version=int(max_version) + 1,
        status="locked",
        source_hash=source_hash,
        source_snapshot=snapshot,
        rubric_json=rubric_json,
        model_name="seed-ai-demo",
        raw_response=json.dumps(rubric_json, ensure_ascii=False),
        locked_at=anchor,
    )
    db.add(rubric)
    db.flush()
    return rubric


def _configure_ai_question(
    db: Session,
    question: JudgeQuestion | ExamQuestion,
    task: dict[str, Any],
    *,
    is_exam: bool,
    anchor: datetime,
) -> None:
    question.grading_mode = "active"
    question.teacher_constraints = {
        "require_function": task["function_name"],
        "seed_ai_demo": True,
    }
    question.reference_solution = task["solution"]
    question.test_groups = _ai_test_groups(task)
    question.score_cap_rules = [
        {"id": "CAP1", "condition_code": "off_topic", "cap": 0, "description": "明显偏离题意时总分上限为 0"},
        {"id": "CAP2", "condition_code": "hardcoded_public_examples", "cap": 20, "description": "硬编码公开样例时总分上限为 20"},
    ]
    _ensure_seed_rubric(db, question, task, is_exam=is_exam, anchor=anchor)


def _create_ai_demo_content(
    db: Session,
    course: Course,
    users: dict[str, Any],
    environments: dict[str, EnvironmentVersion],
    anchor: datetime,
) -> dict[str, int]:
    """为典型课程补充可直接验证的 3 个 AI 作业和 3 个 AI 考试。"""
    teacher_id = users["teacher_zhang"].id
    assignment_count = 0
    assignment_question_count = 0
    exam_count = 0
    exam_code_question_count = 0

    for spec in AI_DEMO_ASSIGNMENT_SPECS:
        task = spec["task"]
        env = environments[spec["environment"]]
        assignment = db.scalar(
            select(Assignment).where(
                Assignment.course_id == course.id,
                Assignment.title == spec["title"],
            )
        )
        if assignment is None:
            assignment = Assignment(
                course_id=course.id,
                title=spec["title"],
                description=spec["description"],
                status="published",
                due_at=anchor + timedelta(days=spec["due_offset"]),
                created_by_id=teacher_id,
                environment_version_id=env.id,
                import_policy_mode="restricted",
                allowed_imports=_allowed_imports_for_environment(spec["environment"]),
            )
            db.add(assignment)
            db.flush()
        else:
            assignment.description = spec["description"]
            assignment.status = "published"
            assignment.due_at = anchor + timedelta(days=spec["due_offset"])
            assignment.environment_version_id = env.id
            assignment.import_policy_mode = "restricted"
            assignment.allowed_imports = _allowed_imports_for_environment(spec["environment"])

        question = db.scalar(
            select(JudgeQuestion)
            .where(JudgeQuestion.assignment_id == assignment.id)
            .order_by(JudgeQuestion.id)
            .limit(1)
        )
        if question is None:
            question = JudgeQuestion(
                assignment_id=assignment.id,
                title=task["title"],
                description=task["description"],
                function_name=task["function_name"],
                signature=task["signature"],
                starter_code=task["starter"],
                public_cases=task["cases"],
                hidden_tests=task["hidden"],
                time_limit_ms=10000,
                memory_limit_mb=max(env.minimum_memory_mb, 512 if spec["environment"] != "torch-cpu" else 2048),
                max_attempts=5,
                environment_version_id=None,
                import_policy_mode="inherit",
                allowed_imports=[],
            )
            db.add(question)
            db.flush()
        _configure_ai_question(db, question, task, is_exam=False, anchor=anchor)
        assignment_count += 1
        assignment_question_count += 1

    for index, spec in enumerate(AI_DEMO_EXAM_SPECS):
        task = spec["task"]
        exam = db.scalar(
            select(Exam).where(
                Exam.course_id == course.id,
                Exam.title == spec["title"],
            )
        )
        start_at = anchor + timedelta(days=spec["start_offset"])
        end_at = anchor + timedelta(days=spec["end_offset"])
        if exam is None:
            exam = Exam(
                course_id=course.id,
                title=spec["title"],
                status="published",
                duration_minutes=60,
                start_at=start_at,
                end_at=end_at,
                created_by_id=teacher_id,
            )
            db.add(exam)
            db.flush()
        else:
            exam.status = "published"
            exam.duration_minutes = 60
            exam.start_at = start_at
            exam.end_at = end_at

        choice = db.scalar(
            select(ExamQuestion).where(
                ExamQuestion.exam_id == exam.id,
                ExamQuestion.order_index == 0,
            )
        )
        if choice is None:
            choice = ExamQuestion(exam_id=exam.id, order_index=0)
            db.add(choice)
        choice.question_type = "single_choice"
        choice.prompt = spec["choice_prompt"]
        choice.options = spec["choice_options"]
        choice.correct_answer = {"correct": spec["choice_answer"]}
        choice.points = 20
        choice.starter_code = None
        choice.public_cases = None
        choice.hidden_tests = None
        choice.grading_mode = "legacy"
        choice.teacher_constraints = {}
        choice.reference_solution = None
        choice.test_groups = []
        choice.score_cap_rules = []

        code = db.scalar(
            select(ExamQuestion).where(
                ExamQuestion.exam_id == exam.id,
                ExamQuestion.order_index == 1,
            )
        )
        if code is None:
            code = ExamQuestion(exam_id=exam.id, order_index=1)
            db.add(code)
        code.question_type = "code"
        code.prompt = f"编程题：{task['description']}"
        code.options = None
        code.correct_answer = {"test_file": task["solution"]}
        code.points = 80
        code.starter_code = task["starter"]
        code.public_cases = task["cases"]
        code.hidden_tests = task["hidden"]
        code.time_limit_ms = 10000
        code.memory_limit_mb = max(environments[spec["environment"]].minimum_memory_mb, 512 if spec["environment"] != "torch-cpu" else 2048)
        db.flush()
        _configure_ai_question(db, code, task, is_exam=True, anchor=anchor)
        exam_count += 1
        exam_code_question_count += 1

    db.flush()
    return {
        "ai_demo_assignments": assignment_count,
        "ai_demo_assignment_questions": assignment_question_count,
        "ai_demo_exams": exam_count,
        "ai_demo_exam_code_questions": exam_code_question_count,
    }


def _create_assignments(
    db: Session,
    users: dict[str, Any],
    courses: dict[str, dict[str, Any]],
    environments: dict[str, EnvironmentVersion],
    anchor: datetime,
) -> dict[str, list[JudgeQuestion]]:
    questions_by_key: dict[str, list[JudgeQuestion]] = {}
    for course_index, (title, item) in enumerate(courses.items()):
        count = 10 if item["typical"] else 2
        for assignment_index in range(count):
            if item["typical"]:
                env_slug = ENVIRONMENT_SLUGS[assignment_index % len(ENVIRONMENT_SLUGS)]
            else:
                env_slug = DOMAIN_ENVIRONMENT[item["domain"]]
            env = environments[env_slug]
            due_at = anchor + timedelta(days=assignment_index - 4)
            assignment = Assignment(
                course_id=item["course"].id,
                title=f"{title}｜第{assignment_index + 1}次作业",
                description=(
                    f"围绕{DOMAIN_TOPICS[item['domain']][assignment_index % 3]}完成代码任务，"
                    "要求提交可运行实现、边界测试和简短实验说明。"
                ),
                status="published",
                due_at=due_at,
                created_by_id=users[item["teacher_key"]].id,
                environment_version_id=env.id,
                import_policy_mode="restricted",
                allowed_imports=(
                    ["pytest"]
                    if env_slug == "basic"
                    else ["numpy", "pandas", "scipy", "sklearn", "matplotlib"]
                    if env_slug == "data"
                    else ["torch"]
                ),
            )
            db.add(assignment)
            db.flush()

            questions: list[JudgeQuestion] = []
            question_count = 3 if item["typical"] else 2
            for question_index in range(question_count):
                task = _task_for_environment(env_slug, assignment_index + question_index)
                question = JudgeQuestion(
                    assignment_id=assignment.id,
                    title=task["title"],
                    description=task["description"],
                    function_name=task["function_name"],
                    signature=task["signature"],
                    starter_code=task["starter"],
                    public_cases=task["cases"],
                    hidden_tests=task["hidden"],
                    time_limit_ms=10000,
                    memory_limit_mb=max(env.minimum_memory_mb, 512 if env_slug != "torch-cpu" else 2048),
                    max_attempts=5,
                    grading_mode="legacy",
                    teacher_constraints={"seed_fixture": True},
                    reference_solution=task["solution"],
                    test_groups=[],
                    score_cap_rules=[],
                    environment_version_id=None,
                    import_policy_mode="inherit",
                    allowed_imports=[],
                )
                db.add(question)
                questions.append(question)
            db.flush()
            questions_by_key[f"{title}:{assignment_index}"] = questions
    return questions_by_key


def _exam_code_question(exam_id: int, order_index: int, task: dict[str, Any], points: float) -> ExamQuestion:
    return ExamQuestion(
        exam_id=exam_id,
        question_type="code",
        prompt=f"编程题：{task['description']}",
        options=None,
        correct_answer={"correct": []},
        points=points,
        order_index=order_index,
        starter_code=task["starter"],
        public_cases=task["cases"],
        hidden_tests=task["hidden"],
        time_limit_ms=10000,
        memory_limit_mb=512,
        grading_mode="legacy",
        teacher_constraints={},
        reference_solution=task["solution"],
        test_groups=[],
        score_cap_rules=[],
    )


def _create_exams(
    db: Session,
    users: dict[str, Any],
    courses: dict[str, dict[str, Any]],
    anchor: datetime,
) -> dict[str, list[ExamQuestion]]:
    questions_by_exam: dict[str, list[ExamQuestion]] = {}
    for course_index, (title, item) in enumerate(courses.items()):
        count = 10 if item["typical"] else 1
        for exam_index in range(count):
            if item["typical"] and exam_index == 0:
                start_at = anchor - timedelta(days=14)
                end_at = anchor - timedelta(days=13, hours=22)
            elif item["typical"] and exam_index == 1:
                start_at = anchor - timedelta(hours=1)
                end_at = anchor + timedelta(hours=2)
            else:
                start_at = anchor + timedelta(days=exam_index + 2)
                end_at = start_at + timedelta(hours=2)
            exam = Exam(
                course_id=item["course"].id,
                title=f"{title}｜第{exam_index + 1}次测验",
                status="published",
                duration_minutes=90,
                start_at=start_at,
                end_at=end_at,
                created_by_id=users[item["teacher_key"]].id,
            )
            db.add(exam)
            db.flush()
            questions: list[ExamQuestion] = []
            questions.append(
                ExamQuestion(
                    exam_id=exam.id,
                    question_type="single_choice",
                    prompt="以下哪一项最能体现可复现实验的基本要求？",
                    options={"A": "只保留最终结论", "B": "固定输入并记录环境", "C": "删除失败结果", "D": "只依赖口头说明"},
                    correct_answer={"correct": ["B"]},
                    points=10,
                    order_index=0,
                )
            )
            questions.append(
                ExamQuestion(
                    exam_id=exam.id,
                    question_type="single_choice",
                    prompt="代码提交前最优先检查哪项内容？",
                    options={"A": "函数签名和边界条件", "B": "变量颜色", "C": "文件名长度", "D": "屏幕分辨率"},
                    correct_answer={"correct": ["A"]},
                    points=10,
                    order_index=1,
                )
            )
            questions.append(
                ExamQuestion(
                    exam_id=exam.id,
                    question_type="multi_choice",
                    prompt="哪些做法有助于定位实验失败原因？（多选）",
                    options={"A": "保存输入", "B": "记录环境版本", "C": "删除错误日志", "D": "保留最小复现样例"},
                    correct_answer={"correct": ["A", "B", "D"]},
                    points=20,
                    order_index=2,
                )
            )
            questions.append(
                _exam_code_question(exam.id, 3, BASIC_TASKS[exam_index % len(BASIC_TASKS)], 30)
            )
            questions.append(
                _exam_code_question(exam.id, 4, BASIC_TASKS[(exam_index + 1) % len(BASIC_TASKS)], 30)
            )
            db.add_all(questions)
            db.flush()
            questions_by_exam[f"{title}:{exam_index}"] = questions
    return questions_by_exam


def _create_assignment_submissions(
    db: Session,
    users: dict[str, Any],
    questions_by_key: dict[str, list[JudgeQuestion]],
    courses: dict[str, dict[str, Any]],
    environments: dict[str, EnvironmentVersion],
    anchor: datetime,
) -> None:
    students: list[User] = users["students"]
    typical_title = TYPICAL_COURSE_TITLE
    teacher = users["teacher_zhang"]
    for assignment_index in range(3):
        questions = questions_by_key[f"{typical_title}:{assignment_index}"]
        for student_index, student in enumerate(students[:4]):
            for question_index, question in enumerate(questions):
                task = _task_for_environment(
                    ENVIRONMENT_SLUGS[assignment_index % len(ENVIRONMENT_SLUGS)],
                    assignment_index + question_index,
                )
                is_wrong = student_index == 1 and question_index == 1
                is_pending = student_index == 2 and question_index == 0
                status = "queued" if is_pending else "wrong_answer" if is_wrong else "accepted"
                score = None if is_pending else 0 if is_wrong else 100
                env_id = question.assignment.environment_version_id
                db.add(
                    Submission(
                        question_id=question.id,
                        student_id=student.id,
                        code=("def pending_solution(*args):\n    pass" if is_pending else task["solution"] if not is_wrong else "def broken_solution():\n    return None"),
                        status=status,
                        grading_status="pending" if is_pending else "completed",
                        attempt_count=0 if is_pending else 1,
                        queued_at=anchor if is_pending else None,
                        finished_at=None if is_pending else anchor,
                        score=score,
                        result_details={"seed_fixture": True, "case": "pending" if is_pending else "wrong" if is_wrong else "accepted"},
                        environment_version_id=env_id,
                        import_policy_mode_snapshot="restricted",
                        allowed_imports_snapshot=list(question.assignment.allowed_imports or []),
                    )
                )
    db.flush()


def _create_exam_submissions(
    db: Session,
    users: dict[str, Any],
    courses: dict[str, dict[str, Any]],
    questions_by_exam: dict[str, list[ExamQuestion]],
    anchor: datetime,
) -> None:
    students: list[User] = users["students"]
    title = TYPICAL_COURSE_TITLE
    for exam_index, status in ((0, "graded"), (1, "started"), (2, "review_required")):
        exam_key = f"{title}:{exam_index}"
        questions = questions_by_exam[exam_key]
        exam = questions[0].exam
        student = students[exam_index]
        started_at = anchor - timedelta(hours=2)
        expires_at = started_at + timedelta(minutes=exam.duration_minutes)
        submission = ExamSubmission(
            exam_id=exam.id,
            student_id=student.id,
            status=status,
            score=100 if status == "graded" else None,
            started_at=started_at,
            expires_at=expires_at,
            submitted_at=anchor - timedelta(minutes=30) if status in ("graded", "review_required") else None,
            graded_at=anchor - timedelta(minutes=10) if status == "graded" else None,
            review_reason="编程题需要教师复核" if status == "review_required" else None,
            review_required_at=anchor if status == "review_required" else None,
        )
        db.add(submission)
        db.flush()
        for question in questions:
            if question.question_type == "single_choice":
                selected = ["B"] if question.order_index == 0 else ["A"]
                score = question.points if status == "graded" else None
                code = None
            elif question.question_type == "multi_choice":
                selected = ["A", "B", "D"]
                score = question.points if status == "graded" else None
                code = None
            else:
                selected = None
                task = BASIC_TASKS[question.order_index % len(BASIC_TASKS)]
                code = task["solution"] if status == "graded" else None
                score = question.points if status == "graded" else None
            db.add(
                ExamAnswer(
                    submission_id=submission.id,
                    question_id=question.id,
                    selected_options=selected,
                    code_answer=code,
                    score=score,
                    grading_status="completed" if status == "graded" else "pending",
                )
            )
        if status == "graded":
            db.add(ExamGrade(exam_id=exam.id, student_id=student.id, score=100))
    db.flush()


def _create_experiment_records(
    db: Session,
    users: dict[str, Any],
    experiments: dict[str, Any],
    notebook_lessons: list[tuple[Lesson, NotebookTemplateVersion]],
    environments: dict[str, EnvironmentVersion],
    anchor: datetime,
) -> None:
    students: list[User] = users["students"]
    modules = experiments["modules"]
    versions_by_template = {
        template.id: version
        for entries in experiments["templates_by_env"].values()
        for template, version in entries
    }

    for index, module in enumerate(modules):
        template = module.notebook_template
        version = versions_by_template[template.id]
        student = students[index]
        sources = {cell["id"]: cell["source"] for cell in version.cells}
        outputs = {
            "exercise": {
                "outputs": [
                    {
                        "msg_type": "stream",
                        "content": {"name": "stdout", "text": "seed experiment output\n"},
                    }
                ],
                "execution_count": 1,
            }
        }
        status = ("started", "submitted", "graded")[index % 3]
        record = ExperimentRecord(
            module_id=module.id,
            lesson_id=None,
            template_version_id=version.id,
            student_id=student.id,
            status=status,
            cells_sources=sources,
            cells_outputs=outputs,
            record_revision=2 if status != "started" else 1,
            started_at=anchor - timedelta(days=1),
            submitted_at=anchor if status in ("submitted", "graded") else None,
            completed_at=anchor if status == "graded" else None,
            environment_version_id=version.environment_version_id,
        )
        db.add(record)
        db.flush()
        if status in ("submitted", "graded"):
            db.add(
                ExperimentSubmission(
                    record_id=record.id,
                    attempt_number=1,
                    client_request_id=str(uuid5(NAMESPACE_URL, f"seed-module:{module.id}:{student.id}")),
                    cells_snapshot=sources,
                    outputs_snapshot=outputs,
                    submitted_at=anchor,
                    score=92 if status == "graded" else None,
                    feedback="代码结构清晰，建议补充一个边界测试。" if status == "graded" else None,
                    reviewed_by_id=users["teacher_zhang"].id if status == "graded" else None,
                    reviewed_at=anchor if status == "graded" else None,
                )
            )

    # 为典型课程的 Notebook 课时创建课程内实验记录，便于验证学生课程详情页。
    for index, (lesson, version) in enumerate(notebook_lessons):
        if index >= 6:
            break
        student = students[0]
        sources = {cell["id"]: cell["source"] for cell in version.cells}
        db.add(
            ExperimentRecord(
                module_id=None,
                lesson_id=lesson.id,
                template_version_id=version.id,
                student_id=student.id,
                status="submitted" if index % 2 else "started",
                cells_sources=sources,
                cells_outputs={},
                record_revision=1,
                started_at=anchor - timedelta(hours=index + 1),
                submitted_at=anchor if index % 2 else None,
                environment_version_id=version.environment_version_id,
            )
        )
    db.flush()


def _count(db: Session, model: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _validate_seed_data(db: Session) -> dict[str, int]:
    teachers = int(db.scalar(select(func.count()).select_from(User).where(User.role == "teacher")) or 0)
    students = int(db.scalar(select(func.count()).select_from(User).where(User.role == "student")) or 0)
    classes = _count(db, TeachingClass)
    courses = _count(db, Course)
    chapters = _count(db, Chapter)
    lessons = _count(db, Lesson)
    assignments = _count(db, Assignment)
    judge_questions = _count(db, JudgeQuestion)
    exams = _count(db, Exam)
    exam_questions = _count(db, ExamQuestion)
    modules = _count(db, ExperimentModule)
    records = _count(db, ExperimentRecord)

    errors: list[str] = []
    if teachers != 3:
        errors.append(f"教师数量应为 3，实际为 {teachers}")
    if students != 400:
        errors.append(f"学生数量应为 400，实际为 {students}")
    if classes != 10:
        errors.append(f"教学班数量应为 10，实际为 {classes}")
    if courses != 30:
        errors.append(f"课程数量应为 30，实际为 {courses}")
    if any(
        int(db.scalar(select(func.count()).select_from(Course).where(Course.teacher_id == user_id)) or 0) != 10
        for user_id in db.scalars(select(User.id).where(User.role == "teacher")).all()
    ):
        errors.append("每位教师必须恰好拥有 10 门课程")

    class_counts = db.execute(
        select(TeachingClass.id, func.count(TeachingClassStudent.id))
        .join(TeachingClassStudent, TeachingClassStudent.teaching_class_id == TeachingClass.id)
        .group_by(TeachingClass.id)
    ).all()
    if len(class_counts) != 10 or any(count != 40 for _, count in class_counts):
        errors.append("每个教学班必须恰好有 40 名学生")

    typical = db.scalar(select(Course).where(Course.title == TYPICAL_COURSE_TITLE))
    if typical is None:
        errors.append("典型课程不存在")
    else:
        typical_chapters = int(db.scalar(select(func.count()).select_from(Chapter).where(Chapter.course_id == typical.id)) or 0)
        typical_lessons = int(
            db.scalar(
                select(func.count()).select_from(Lesson).join(Chapter).where(Chapter.course_id == typical.id)
            )
            or 0
        )
        typical_assignments = _count_query(db, Assignment, Assignment.course_id == typical.id)
        typical_exams = _count_query(db, Exam, Exam.course_id == typical.id)
        ai_demo_assignment_titles = [spec["title"] for spec in AI_DEMO_ASSIGNMENT_SPECS]
        ai_demo_exam_titles = [spec["title"] for spec in AI_DEMO_EXAM_SPECS]
        ai_demo_assignments = int(
            db.scalar(select(func.count()).select_from(Assignment).where(Assignment.title.in_(ai_demo_assignment_titles))) or 0
        )
        ai_demo_exams = int(
            db.scalar(select(func.count()).select_from(Exam).where(Exam.title.in_(ai_demo_exam_titles))) or 0
        )
        ai_demo_assignment_questions = int(
            db.scalar(
                select(func.count())
                .select_from(JudgeQuestion)
                .join(Assignment)
                .where(Assignment.title.in_(ai_demo_assignment_titles), JudgeQuestion.grading_mode == "active")
            )
            or 0
        )
        ai_demo_exam_code_questions = int(
            db.scalar(
                select(func.count())
                .select_from(ExamQuestion)
                .join(Exam)
                .where(
                    Exam.title.in_(ai_demo_exam_titles),
                    ExamQuestion.question_type == "code",
                    ExamQuestion.grading_mode == "active",
                )
            )
            or 0
        )
        ai_demo_locked_rubrics = int(
            db.scalar(select(func.count()).select_from(QuestionRubric).where(QuestionRubric.status == "locked")) or 0
        )
        if typical_chapters < 6 or typical_lessons < 24:
            errors.append("典型课程必须至少有 6 个章节和 24 个课时")
        if typical_assignments < 10:
            errors.append("典型课程作业数量不足 10 个")
        if typical_exams < 10:
            errors.append("典型课程考试数量不足 10 个")

        if ai_demo_assignments != 3 or ai_demo_assignment_questions != 3:
            errors.append("典型课程必须包含 3 个 AI 评分演示作业及其编程题")
        if ai_demo_exams != 3 or ai_demo_exam_code_questions != 3:
            errors.append("典型课程必须包含 3 个 AI 评分演示考试及其编程题")
        if ai_demo_locked_rubrics < 6:
            errors.append("AI 评分演示编程题必须全部存在锁定 Rubric")

    lesson_types = set(db.scalars(select(Lesson.content_type).distinct()).all())
    if not {"markdown", "video", "notebook"}.issubset(lesson_types):
        errors.append("课程课时必须覆盖 markdown、video、notebook 三种类型")
    if modules < 12:
        errors.append("实验模块数量不足 12 个")
    if records < 12:
        errors.append("实验记录数量不足 12 条")

    if errors:
        raise RuntimeError("种子数据校验失败：" + "；".join(errors))

    return {
        "teachers": teachers,
        "students": students,
        "classes": classes,
        "courses": courses,
        "chapters": chapters,
        "lessons": lessons,
        "assignments": assignments,
        "judge_questions": judge_questions,
        "exams": exams,
        "exam_questions": exam_questions,
        "experiment_modules": modules,
        "experiment_records": records,
        "submissions": _count(db, Submission),
        "exam_submissions": _count(db, ExamSubmission),
        "experiment_submissions": _count(db, ExperimentSubmission),
        "ai_demo_assignments": ai_demo_assignments if typical is not None else 0,
        "ai_demo_assignment_questions": ai_demo_assignment_questions if typical is not None else 0,
        "ai_demo_exams": ai_demo_exams if typical is not None else 0,
        "ai_demo_exam_code_questions": ai_demo_exam_code_questions if typical is not None else 0,
        "ai_demo_locked_rubrics": ai_demo_locked_rubrics if typical is not None else 0,
    }


def _count_query(db: Session, model: Any, criterion: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(criterion)) or 0)


def seed_internal_test_data(db: Session, environments: dict[str, EnvironmentVersion]) -> dict[str, int]:
    anchor = _now()
    _clear_business_data(db)
    users = _create_users(db)
    academics = _create_academics(db, users, anchor)
    experiments = _create_experiments(db, users, environments)
    courses, notebook_lessons = _create_courses(db, users, academics, experiments, anchor)
    _create_enrollments(db, academics, courses, users)
    questions_by_key = _create_assignments(db, users, courses, environments, anchor)
    _create_assignment_submissions(db, users, questions_by_key, courses, environments, anchor)
    questions_by_exam = _create_exams(db, users, courses, anchor)
    _create_exam_submissions(db, users, courses, questions_by_exam, anchor)
    ai_demo_summary = _create_ai_demo_content(
        db,
        courses[TYPICAL_COURSE_TITLE]["course"],
        users,
        environments,
        anchor,
    )
    _create_experiment_records(db, users, experiments, notebook_lessons, environments, anchor)
    db.flush()
    db.execute(
        update(Assignment)
        .where(Assignment.status == "published", Assignment.published_at.is_(None))
        .values(published_at=Assignment.created_at)
    )
    db.flush()
    summary = _validate_seed_data(db)
    summary.update(ai_demo_summary)
    return summary


def seed_ai_demo_data(db: Session, environments: dict[str, EnvironmentVersion]) -> dict[str, int]:
    """只补充/修复典型课程的 AI 评分演示数据，不清理现有业务数据。"""
    course = db.scalar(select(Course).where(Course.title == TYPICAL_COURSE_TITLE))
    if course is None:
        raise RuntimeError(f"找不到典型课程：{TYPICAL_COURSE_TITLE}，请先执行全量内测种子")
    teacher = db.scalar(select(User).where(User.username == "teacher_zhang", User.role == "teacher"))
    if teacher is None:
        raise RuntimeError("找不到典型教师 teacher_zhang，请先执行全量内测种子")
    summary = _create_ai_demo_content(
        db,
        course,
        {"teacher_zhang": teacher},
        environments,
        _now(),
    )
    db.flush()
    db.execute(
        update(Assignment)
        .where(Assignment.status == "published", Assignment.published_at.is_(None))
        .values(published_at=Assignment.created_at)
    )
    db.flush()
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DAI 生产前内测全量种子数据")
    parser.add_argument(
        "--confirm-internal-reset",
        action="store_true",
        help="确认清理并重建业务内测数据",
    )
    parser.add_argument(
        "--augment-ai-demo",
        action="store_true",
        help="仅为典型课程补充 3 个 AI 作业和 3 个 AI 考试，不清理现有数据",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    if settings.environment == "production":
        raise SystemExit("拒绝执行：DAI_ENVIRONMENT=production，不允许运行内测重置种子。")
    if args.augment_ai_demo and args.confirm_internal_reset:
        raise SystemExit("--augment-ai-demo 与 --confirm-internal-reset 不能同时使用")
    if not args.confirm_internal_reset:
        if args.augment_ai_demo:
            db = SessionLocal()
            try:
                environments = _environment_map(db)
                summary = seed_ai_demo_data(db, environments)
                db.commit()
                print("DAI 典型课程 AI 评分演示数据已补充完成")
                for key, value in summary.items():
                    print(f"{key:32s}: {value}")
                print("\n作业/考试均为已发布状态，编程题 grading_mode=active，Rubric 已锁定。")
                return 0
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        raise SystemExit(
            "未执行任何数据库操作。请使用 --confirm-internal-reset 明确确认这是一次内测业务数据重置。"
        )

    db = SessionLocal()
    try:
        # 必须先解析环境，确保环境缺失时不会清理已有业务数据。
        environments = _environment_map(db)
        summary = seed_internal_test_data(db, environments)
        db.commit()
        print("=" * 64)
        print("DAI 实验平台 —— 生产前内测种子数据已完成")
        print("=" * 64)
        for key, value in summary.items():
            print(f"{key:24s}: {value}")
        print("\n账号密码可由 DAI_SEED_*_PASSWORD 环境变量覆盖。")
        print("教师账号: teacher_zhang / teacher_chen / teacher_zhao")
        print("学生账号示例: student_24621600_01")
        print("默认密码: Test1234!")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
