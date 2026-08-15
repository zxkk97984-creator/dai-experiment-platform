# -*- coding: utf-8 -*-
"""Demo 题库与实验模板内容（固定常量，评审 4 稳定数据源）。

题目来自项目旧内测种子（git show 9e905eb:backend/app/seed_data.py）中的
BASIC_TASKS / DATA_TASKS / TORCH_TASKS 与 EXPERIMENT_SPECS，内容经核对保持
可判题（隐藏测试与参考答案一致）。
"""
from __future__ import annotations

# ── 基础判题任务（basic 环境） ─────────────────────────────────────────────
BASIC_TASKS = [
    {
        "title": "正数求和",
        "function_name": "sum_positive",
        "signature": "def sum_positive(values: list[int]) -> int:",
        "description": "返回列表中所有正数的和；空列表返回 0。",
        "starter": "def sum_positive(values):\n    pass",
        "cases": [{"args": [[-2, 3, 4]], "expected": 7}, {"args": [[]], "expected": 0}],
        "hidden": (
            "import user_code\n\n"
            "def test_positive_and_negative():\n"
            "    assert user_code.sum_positive([-2, 3, 4]) == 7\n\n"
            "def test_empty():\n"
            "    assert user_code.sum_positive([]) == 0\n\n"
            "def test_all_negative():\n"
            "    assert user_code.sum_positive([-5, -1]) == 0\n"
        ),
        "solution": "def sum_positive(values):\n    return sum(v for v in values if v > 0)",
    },
    {
        "title": "括号匹配",
        "function_name": "is_balanced",
        "signature": "def is_balanced(text: str) -> bool:",
        "description": "判断字符串中的圆括号、方括号和花括号是否正确嵌套。",
        "starter": "def is_balanced(text):\n    pass",
        "cases": [{"args": ["([])"], "expected": True}, {"args": ["([)]"], "expected": False}],
        "hidden": (
            "import user_code\n\n"
            "def test_nested():\n"
            "    assert user_code.is_balanced('{[()]}') is True\n\n"
            "def test_mismatch():\n"
            "    assert user_code.is_balanced('([)]') is False\n\n"
            "def test_empty():\n"
            "    assert user_code.is_balanced('') is True\n"
        ),
        "solution": (
            "def is_balanced(text):\n"
            "    pairs = {')': '(', ']': '[', '}': '{'}\n"
            "    stack = []\n"
            "    for char in text:\n"
            "        if char in '([{':\n"
            "            stack.append(char)\n"
            "        elif char in pairs and (not stack or stack.pop() != pairs[char]):\n"
            "            return False\n"
            "    return not stack"
        ),
    },
    {
        "title": "二分查找",
        "function_name": "binary_search",
        "signature": "def binary_search(values: list[int], target: int) -> int:",
        "description": "在升序整数列表中查找目标值，返回下标；不存在时返回 -1。",
        "starter": "def binary_search(values, target):\n    pass",
        "cases": [{"args": [[1, 3, 5, 7], 5], "expected": 2}, {"args": [[], 1], "expected": -1}],
        "hidden": (
            "import user_code\n\n"
            "def test_found():\n"
            "    assert user_code.binary_search([1, 3, 5, 7], 5) == 2\n\n"
            "def test_missing():\n"
            "    assert user_code.binary_search([1, 3, 5, 7], 6) == -1\n\n"
            "def test_empty():\n"
            "    assert user_code.binary_search([], 1) == -1\n"
        ),
        "solution": (
            "def binary_search(values, target):\n"
            "    left, right = 0, len(values) - 1\n"
            "    while left <= right:\n"
            "        mid = (left + right) // 2\n"
            "        if values[mid] == target:\n"
            "            return mid\n"
            "        if values[mid] < target:\n"
            "            left = mid + 1\n"
            "        else:\n"
            "            right = mid - 1\n"
            "    return -1"
        ),
    },
]

# ── 数据任务（data 环境；仅当 data 档位可用时启用） ─────────────────────────
DATA_TASKS = [
    {
        "title": "向量标准化",
        "function_name": "zscore",
        "signature": "def zscore(values: list[float]) -> list[float]:",
        "description": "使用 NumPy 返回均值为 0、标准差为 1 的标准化向量。",
        "starter": "def zscore(values):\n    import numpy as np\n    pass",
        "cases": [{"args": [[1.0, 2.0, 3.0]], "expected": [-1.2247, 0.0, 1.2247]}],
        "hidden": (
            "import numpy as np\n"
            "import user_code\n\n"
            "def test_zscore():\n"
            "    result = np.array(user_code.zscore([1.0, 2.0, 3.0]))\n"
            "    assert np.allclose(result, [-1.22474487, 0.0, 1.22474487])\n"
        ),
        "solution": (
            "def zscore(values):\n"
            "    import numpy as np\n"
            "    array = np.asarray(values, dtype=float)\n"
            "    return ((array - array.mean()) / array.std()).tolist()"
        ),
    },
    {
        "title": "填充缺失成绩",
        "function_name": "fill_missing_scores",
        "signature": "def fill_missing_scores(values: list[float | None]) -> list[float]:",
        "description": "使用 Pandas 以非缺失成绩均值填充缺失值。",
        "starter": "def fill_missing_scores(values):\n    import pandas as pd\n    pass",
        "cases": [{"args": [[80, None, 100]], "expected": [80.0, 90.0, 100.0]}],
        "hidden": (
            "import pandas as pd\n"
            "import user_code\n\n"
            "def test_fill_mean():\n"
            "    result = user_code.fill_missing_scores([80, None, 100])\n"
            "    assert result == [80.0, 90.0, 100.0]\n\n"
            "def test_no_missing():\n"
            "    assert user_code.fill_missing_scores([1, 2]) == [1.0, 2.0]\n"
        ),
        "solution": (
            "def fill_missing_scores(values):\n"
            "    import pandas as pd\n"
            "    s = pd.Series(values, dtype='float64')\n"
            "    return s.fillna(s.mean()).tolist()"
        ),
    },
]

# ── AI 评分演示任务（basic 环境，F/R 测试组） ───────────────────────────────
# 与 DATA_TASKS/BASIC_TASKS 配合：AI 评分作业使用 basic 环境可判题的任务
AI_TASKS = BASIC_TASKS + DATA_TASKS

# 各任务对应的鲁棒性测试组（R 维度，10 分）
AI_ROBUSTNESS_TESTS = {
    "sum_positive": (
        "def test_robustness_float():\n"
        "    assert user_code.sum_positive([1.5, -2, 3]) == 4.5\n"
    ),
    "is_balanced": (
        "def test_robustness_long():\n"
        "    assert user_code.is_balanced('(((([]))))') is True\n"
    ),
    "binary_search": (
        "def test_robustness_dup():\n"
        "    assert user_code.binary_search([1, 1, 2, 2, 3], 2) >= 2\n"
    ),
    "zscore": (
        "def test_robustness_single():\n"
        "    result = user_code.zscore([5.0])\n"
        "    assert len(result) == 1 and abs(result[0]) < 1e-9\n"
    ),
    "fill_missing_scores": (
        "def test_robustness_all_missing():\n"
        "    result = user_code.fill_missing_scores([None, None])\n"
        "    assert result == [0.0, 0.0]\n"
    ),
}

# ── 实验模板内容（EXPERIMENT_SPECS 精简版，basic 环境） ─────────────────────
EXPERIMENT_SPECS = [
    {
        "name": "基础环境：函数与单元测试",
        "objective": "编写一个可测试的统计函数，并使用 pytest 验证边界条件。",
        "imports": ["pytest"],
        "setup": "import pytest\n\ndef assert_close(actual, expected):\n    assert actual == expected",
        "exercise": "def average(values):\n    \"\"\"返回非空数值列表的平均值。\"\"\"\n    pass\n\nprint(average([1, 2, 3, 4]))",
        "expected": "2.5",
    },
    {
        "name": "基础环境：列表与字典",
        "objective": "使用列表、字典和集合完成成绩汇总，关注空输入与重复数据。",
        "imports": [],
        "setup": "scores = [{\"name\": \"A\", \"score\": 88}, {\"name\": \"B\", \"score\": 92}]",
        "exercise": "def top_student(scores):\n    pass\n\nprint(top_student(scores))",
        "expected": "B",
    },
    {
        "name": "基础环境：排序与查找",
        "objective": "实现二分查找，并通过有序、空列表和重复值场景验证算法。",
        "imports": [],
        "setup": "items = [2, 4, 7, 11, 18, 25]",
        "exercise": "def binary_search(items, target):\n    pass\n\nprint(binary_search(items, 11))",
        "expected": "3",
    },
    {
        "name": "基础环境：pytest 边界测试",
        "objective": "为字符串规范化函数补充参数化测试，理解测试夹具和断言。",
        "imports": ["pytest"],
        "setup": "cases = [(\" Hello \", \"hello\"), (\"WORLD\", \"world\"), (\"\", \"\")]",
        "exercise": "def normalize_text(value):\n    pass\n\nfor raw, expected in cases:\n    print(normalize_text(raw) == expected)",
        "expected": "True\nTrue\nTrue",
    },
]
