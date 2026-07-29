"""DAI 验收演示数据脚本

通过 /api/v1 接口创建可重复的验收数据。所有资源以精确的 [验收] 标题和
固定用户名实现幂等，不直接操作数据库。

用法:
    .venv\\Scripts\\python.exe seed_acceptance_data.py --base-url http://localhost:8080/api/v1
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

# ═══════════════════════════════════════════════════════════════════════════════
# 异常
# ═══════════════════════════════════════════════════════════════════════════════


class SeedError(Exception):
    """验收数据脚本错误"""


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════


def find_exact(items: list[dict], field: str, value: Any) -> dict | None:
    """在列表中按字段精确匹配，返回第一个匹配项或 None。"""
    for item in items:
        if item.get(field) == value:
            return item
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 固定演示账号
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_STUDENTS: list[dict[str, str]] = [
    {"username": "accept_student_a", "real_name": "验收学生甲", "role": "student"},
    {"username": "accept_student_b", "real_name": "验收学生乙", "role": "student"},
]

# ═══════════════════════════════════════════════════════════════════════════════
# 完整验收数据
# ═══════════════════════════════════════════════════════════════════════════════

CST = timezone(timedelta(hours=8))
EXAM_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=CST)
EXAM_END = datetime(2027, 12, 31, 23, 59, 59, tzinfo=CST)


def _mc_opts(*labels: str) -> dict:
    """构建选择题选项 {"A": "…", "B": "…", …}"""
    return {chr(65 + i): v for i, v in enumerate(labels)}


ACCEPTANCE_DATA: list[dict] = [
    {
        "title": "[验收] Python 算法与工程实践",
        "description": (
            "本课程覆盖 Python 基础语法、数据结构、经典算法与工程实践，"
            "通过系统化的章节编排和配套编程练习，帮助学生掌握扎实的编程功底。"
        ),
        "chapters": [
            {
                "title": "Python 基础与代码规范",
                "order_index": 0,
                "lessons": [
                    {
                        "title": "函数设计与类型约定",
                        "content_type": "markdown",
                        "content": (
                            "# 函数设计与类型约定\n\n"
                            "## 学习目标\n\n"
                            "- 理解单一职责原则在函数设计中的应用\n"
                            "- 掌握 Python 类型注解的基本语法\n"
                            "- 能够编写清晰、可维护的函数签名\n\n"
                            "## 核心知识\n\n"
                            "### 单一职责原则\n\n"
                            "每个函数应该只做一件事，并且把它做好。如果函数名中出现了「和」字，"
                            "通常意味着它承担了太多职责。\n\n"
                            "### 类型注解\n\n"
                            "Python 3.5+ 支持类型注解，帮助 IDE 和静态检查工具发现潜在问题：\n\n"
                            "```python\ndef normalize_name(name: str) -> str:\n"
                            '    """规范化姓名：去除首尾空白，转为首字母大写"""\n'
                            "    return name.strip().title()\n"
                            "```\n\n"
                            "## 示例\n\n"
                            "```python\n"
                            "# 好的设计：函数签名自解释\n"
                            "def calculate_average(scores: list[float]) -> float:\n"
                            "    if not scores:\n"
                            "        return 0.0\n"
                            "    return sum(scores) / len(scores)\n"
                            "```\n\n"
                            "## 练习\n\n"
                            "1. 为以下无类型注解的函数添加正确的类型注解\n"
                            "2. 重构一个承担多职责的函数，将其拆分为多个单一职责函数\n"
                            "3. 编写一个带有完整类型注解的模块"
                        ),
                    },
                    {
                        "title": "输入验证与异常处理",
                        "content_type": "markdown",
                        "content": (
                            "# 输入验证与异常处理\n\n"
                            "## 学习目标\n\n"
                            "- 掌握输入验证的最佳实践\n"
                            "- 理解 EAFP（请求原谅比请求许可更容易）与 LBYL 的区别\n"
                            "- 能够编写健壮的异常处理代码\n\n"
                            "## 核心知识\n\n"
                            "### 输入验证\n\n"
                            "永远不要信任外部输入。函数入口处应验证参数类型、范围和约束条件。\n\n"
                            "### 异常处理模式\n\n"
                            "```python\ndef safe_divide(a: float, b: float) -> float:\n"
                            '    """安全除法，分母为零时抛出有意义的异常"""\n'
                            "    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):\n"
                            "        raise TypeError('参数必须是数字')\n"
                            "    if b == 0:\n"
                            "        raise ValueError('分母不能为零')\n"
                            "    return a / b\n"
                            "```\n\n"
                            "## 示例\n\n"
                            "使用 try/except 处理可恢复错误，让调用者决定如何处理异常情况。\n\n"
                            "## 练习\n\n"
                            "1. 编写带输入验证的函数\n"
                            "2. 区分可恢复错误与不可恢复错误\n"
                            "3. 设计自定义异常类层次结构"
                        ),
                    },
                ],
            },
            {
                "title": "数据结构与复杂度",
                "order_index": 1,
                "lessons": [
                    {
                        "title": "列表、字典与集合",
                        "content_type": "markdown",
                        "content": (
                            "# 列表、字典与集合\n\n"
                            "## 学习目标\n\n"
                            "- 掌握三种核心内置数据结构的特性和适用场景\n"
                            "- 理解各数据结构的底层实现与时间复杂度\n"
                            "- 能够根据需求选择最优数据结构\n\n"
                            "## 核心知识\n\n"
                            "### 列表 (list)\n\n"
                            "动态数组，支持随机访问 O(1)，插入/删除 O(n)。适合频繁索引、"
                            "较少中间插入的场景。\n\n"
                            "### 字典 (dict)\n\n"
                            "哈希表实现，查找/插入/删除均为 O(1) 平均。适合键值映射和"
                            "计数统计。\n\n"
                            "### 集合 (set)\n\n"
                            "基于哈希表，元素唯一。适合去重、成员检查和集合运算。\n\n"
                            "## 示例\n\n"
                            "```python\n"
                            "# 使用集合进行高效去重\n"
                            "def deduplicate_ordered(items: list) -> list:\n"
                            '    """保持原始顺序的去重"""\n'
                            "    seen = set()\n"
                            "    result = []\n"
                            "    for item in items:\n"
                            "        if item not in seen:\n"
                            "            seen.add(item)\n"
                            "            result.append(item)\n"
                            "    return result\n"
                            "```\n\n"
                            "## 练习\n\n"
                            "1. 比较列表推导式与生成器表达式的内存使用\n"
                            "2. 使用字典实现词频统计\n"
                            "3. 用集合运算找出两个列表的交集和差集"
                        ),
                    },
                    {
                        "title": "时间复杂度分析",
                        "content_type": "markdown",
                        "content": (
                            "# 时间复杂度分析\n\n"
                            "## 学习目标\n\n"
                            "- 理解大 O 表示法的含义\n"
                            "- 能够分析常见算法的时间与空间复杂度\n"
                            "- 学会在效率与可读性之间做权衡\n\n"
                            "## 核心知识\n\n"
                            "### 常见复杂度级别\n\n"
                            "| 复杂度 | 典型算法 | 可处理规模 |\n"
                            "|--------|---------|----------|\n"
                            "| O(1) | 哈希查找 | 任意 |\n"
                            "| O(log n) | 二分查找 | ~10^9 |\n"
                            "| O(n) | 线性扫描 | ~10^7 |\n"
                            "| O(n log n) | 归并排序 | ~10^6 |\n"
                            "| O(n²) | 冒泡排序 | ~10^4 |\n\n"
                            "## 示例\n\n"
                            "二分查找的时间复杂度分析：每次比较将搜索空间减半，"
                            "最坏情况下需要 log₂(n) 次比较。\n\n"
                            "## 练习\n\n"
                            "1. 分析去重操作的三种实现的时间复杂度\n"
                            "2. 测量实际运行时间验证复杂度分析\n"
                            "3. 优化一个 O(n²) 算法到 O(n log n)"
                        ),
                    },
                ],
            },
            {
                "title": "经典算法实战",
                "order_index": 2,
                "lessons": [
                    {
                        "title": "排序、二分与边界处理",
                        "content_type": "markdown",
                        "content": (
                            "# 排序、二分与边界处理\n\n"
                            "## 学习目标\n\n"
                            "- 掌握二分查找及其变体\n"
                            "- 理解排序算法的选择依据\n"
                            "- 能够正确处理边界条件\n\n"
                            "## 核心知识\n\n"
                            "### 二分查找的边界陷阱\n\n"
                            "二分查找看似简单，但边界处理极易出错：\n"
                            "- 使用 `left <= right` 还是 `left < right`？\n"
                            "- mid 计算防止溢出：`mid = left + (right - left) // 2`\n"
                            "- 更新边界时是 `mid` 还是 `mid ± 1`？\n\n"
                            "## 示例\n\n"
                            "```python\n"
                            "def binary_search(arr: list[int], target: int) -> int:\n"
                            '    """标准二分查找，返回索引，未找到返回 -1"""\n'
                            "    left, right = 0, len(arr) - 1\n"
                            "    while left <= right:\n"
                            "        mid = left + (right - left) // 2\n"
                            "        if arr[mid] == target:\n"
                            "            return mid\n"
                            "        elif arr[mid] < target:\n"
                            "            left = mid + 1\n"
                            "        else:\n"
                            "            right = mid - 1\n"
                            "    return -1\n"
                            "```\n\n"
                            "## 练习\n\n"
                            "1. 实现查找第一个等于 target 的位置\n"
                            "2. 实现查找最后一个小于 target 的位置\n"
                            "3. 在旋转排序数组中查找目标值"
                        ),
                    },
                    {
                        "title": "算法性能实验",
                        "content_type": "markdown",
                        "content": (
                            "# 算法性能实验\n\n"
                            "## 学习目标\n\n"
                            "- 掌握 timeit 模块的使用\n"
                            "- 能够设计性能对比实验\n"
                            "- 学会解读实验结果\n\n"
                            "## 核心知识\n\n"
                            "### 性能测量方法\n\n"
                            "使用 `timeit` 模块进行精确测量，避免单次测量的偶然误差。"
                            "注意预热 JIT、控制变量和重复实验。\n\n"
                            "## 示例\n\n"
                            "对比列表推导式与循环构建的性能差异。\n\n"
                            "## 练习\n\n"
                            "1. 对三种去重方法进行性能基准测试\n"
                            "2. 分析不同规模输入下的增长趋势\n"
                            "3. 撰写实验报告总结发现"
                        ),
                    },
                ],
            },
        ],
        "assignments": [
            {
                "title": "[验收] 作业一 Python 基础",
                "description": "Python 基础函数设计与输入验证练习",
                "questions": [
                    {
                        "title": "规范化姓名",
                        "description": "编写函数 normalize_name(name: str) -> str，将输入的姓名规范化：去除首尾空白，将每个单词的首字母转为大写，其余字母小写。如果输入为空字符串或只含空白，返回空字符串。",
                        "function_name": "normalize_name",
                        "signature": "def normalize_name(name: str) -> str",
                        "starter_code": "def normalize_name(name: str) -> str:\n    # 去除首尾空白并规范化大小写\n    pass\n",
                        "public_cases": [
                            {"args": ["  john DOE  "], "expected": "John Doe"},
                            {"args": ["mary jane"], "expected": "Mary Jane"},
                            {"args": [""], "expected": ""},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    assert normalize_name('  ') == ''\n"
                            "    assert normalize_name('a') == 'A'\n"
                            "    # no hidden test with embedded quote\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "legacy",
                    },
                    {
                        "title": "安全除法",
                        "description": "编写函数 safe_divide(a: float, b: float) -> float，计算 a/b。当 b 为 0 时抛出 ValueError('分母不能为零')，当参数非数字时抛出 TypeError。",
                        "function_name": "safe_divide",
                        "signature": "def safe_divide(a: float, b: float) -> float",
                        "starter_code": "def safe_divide(a: float, b: float) -> float:\n    # 安全除法：验证参数并处理除零\n    pass\n",
                        "public_cases": [
                            {"args": [10.0, 2.0], "expected": 5.0},
                            {"args": [7.0, 2.0], "expected": 3.5},
                        ],
                        "hidden_tests": (
                            "import pytest\n"
                            "def test_hidden():\n"
                            "    assert safe_divide(-6.0, 3.0) == -2.0\n"
                            "    with pytest.raises(ValueError):\n"
                            "        safe_divide(1.0, 0.0)\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "shadow",
                    },
                    {
                        "title": "成绩摘要",
                        "description": "编写函数 summarize_scores(scores: list[float]) -> dict，传入分数列表，返回包含 min（最低分）、max（最高分）、avg（平均分，保留两位小数）、count（数量）的字典。空列表时 min 和 max 为 None，avg 为 0.0。",
                        "function_name": "summarize_scores",
                        "signature": "def summarize_scores(scores: list[float]) -> dict",
                        "starter_code": "def summarize_scores(scores: list[float]) -> dict:\n    # 统计成绩摘要信息\n    pass\n",
                        "public_cases": [
                            {"args": [[85.0, 92.0, 78.0, 90.0]], "expected": {"min": 78.0, "max": 92.0, "avg": 86.25, "count": 4}},
                            {"args": [[]], "expected": {"min": None, "max": None, "avg": 0.0, "count": 0}},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    assert summarize_scores([100.0]) == {'min': 100.0, 'max': 100.0, 'avg': 100.0, 'count': 1}\n"
                            "    r = summarize_scores([60.0, 60.0, 60.0])\n"
                            "    assert r['min'] == r['max'] == r['avg'] == 60.0\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "active",
                    },
                ],
            },
            {
                "title": "[验收] 作业二 数据结构与算法",
                "description": "数据结构与基础算法编程练习",
                "questions": [
                    {
                        "title": "有序去重",
                        "description": "编写函数 deduplicate_ordered(items: list) -> list，保持原始顺序去除重复元素。使用集合辅助实现 O(n) 时间复杂度。",
                        "function_name": "deduplicate_ordered",
                        "signature": "def deduplicate_ordered(items: list) -> list",
                        "starter_code": "def deduplicate_ordered(items: list) -> list:\n    # 保持顺序去重，O(n) 实现\n    pass\n",
                        "public_cases": [
                            {"args": [[1, 2, 2, 3, 1]], "expected": [1, 2, 3]},
                            {"args": [["a", "b", "a"]], "expected": ["a", "b"]},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    assert deduplicate_ordered([]) == []\n"
                            "    assert deduplicate_ordered([None, 0, None]) == [None, 0]\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "legacy",
                    },
                    {
                        "title": "词频统计",
                        "description": "编写函数 word_frequency(text: str) -> dict[str, int]，统计英文文本中每个单词出现次数。单词以空格分隔，忽略大小写，去除标点符号。",
                        "function_name": "word_frequency",
                        "signature": "def word_frequency(text: str) -> dict[str, int]",
                        "starter_code": "def word_frequency(text: str) -> dict[str, int]:\\n    # 统计英文文本中的词频\\n    pass\\n",
                        "public_cases": [
                            {"args": ["hello world hello"], "expected": {"hello": 2, "world": 1}},
                            {"args": ["a a b"], "expected": {"a": 2, "b": 1}},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    assert word_frequency('') == {}\n"
                            "    r = word_frequency('Hello, World! Hello.')\n"
                            "    assert r.get('hello') == 2\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "shadow",
                    },
                    {
                        "title": "二分查找",
                        "description": "编写函数 binary_search(arr: list[int], target: int) -> int，在升序数组中二分查找目标值，返回索引。未找到返回 -1。假设输入数组已排序且无重复元素。",
                        "function_name": "binary_search",
                        "signature": "def binary_search(arr: list[int], target: int) -> int",
                        "starter_code": "def binary_search(arr: list[int], target: int) -> int:\n    # 二分查找，返回索引或 -1\n    pass\n",
                        "public_cases": [
                            {"args": [[1, 3, 5, 7, 9], 5], "expected": 2},
                            {"args": [[1, 3, 5, 7, 9], 2], "expected": -1},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    assert binary_search([], 1) == -1\n"
                            "    assert binary_search([10], 10) == 0\n"
                            "    assert binary_search([10], 5) == -1\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "active",
                    },
                ],
            },
        ],
        "exams": [
            {
                "title": "[验收] Python 阶段考试",
                "duration_minutes": 90,
                "start_at": EXAM_START.isoformat(),
                "end_at": EXAM_END.isoformat(),
                "questions": [
                    {
                        "question_type": "single_choice",
                        "prompt": "Python 中，以下哪个数据结构查找元素的平均时间复杂度最低？",
                        "options": {"A": "列表 (list)", "B": "集合 (set)", "C": "元组 (tuple)", "D": "字符串 (str)"},
                        "correct_answer": {"correct": ["B"]},
                        "points": 5,
                        "order_index": 0,
                    },
                    {
                        "question_type": "single_choice",
                        "prompt": "二分查找的前提条件是？",
                        "options": {"A": "数据必须存储在链表中", "B": "数据必须已排序", "C": "数据量必须大于1000", "D": "数据不能有重复元素"},
                        "correct_answer": {"correct": ["B"]},
                        "points": 5,
                        "order_index": 1,
                    },
                    {
                        "question_type": "multi_choice",
                        "prompt": "以下哪些是 Python 类型注解的优点？（多选）",
                        "options": {"A": "提升代码可读性", "B": "帮助 IDE 自动补全", "C": "静态检查工具可以发现类型错误", "D": "运行时自动强制类型检查"},
                        "correct_answer": {"correct": ["A", "B", "C"]},
                        "points": 10,
                        "order_index": 2,
                    },
                    {
                        "question_type": "multi_choice",
                        "prompt": "以下关于异常处理的描述，哪些是正确的？（多选）",
                        "options": {"A": "try/except 用于处理可恢复错误", "B": "捕获所有异常使用 except Exception", "C": "finally 块中的代码总是会执行", "D": "异常处理不会影响程序性能"},
                        "correct_answer": {"correct": ["A", "C"]},
                        "points": 10,
                        "order_index": 3,
                    },
                    {
                        "question_type": "code",
                        "prompt": "编写函数 merge_intervals(intervals: list[list[int]]) -> list[list[int]]，合并所有重叠的区间。每个区间表示为 [start, end]（闭区间）。假设输入已按 start 排序。",
                        "points": 35,
                        "order_index": 4,
                        "starter_code": "def merge_intervals(intervals):\n    # 合并重叠区间\n    if not intervals:\n        return []\n    result = [intervals[0]]\n    for curr in intervals[1:]:\n        prev = result[-1]\n        if curr[0] <= prev[1]:\n            prev[1] = max(prev[1], curr[1])\n        else:\n            result.append(curr)\n    return result\n",
                        "public_cases": [
                            {"args": [[[1, 3], [2, 6], [8, 10]]], "expected": [[1, 6], [8, 10]]},
                            {"args": [[[1, 4], [4, 5]]], "expected": [[1, 5]]},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    assert merge_intervals([]) == []\n"
                            "    assert merge_intervals([[1, 2]]) == [[1, 2]]\n"
                            "    assert merge_intervals([[1, 5], [2, 3], [4, 6]]) == [[1, 6]]\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "legacy",
                    },
                    {
                        "question_type": "code",
                        "prompt": "编写函数 balanced_brackets(s: str) -> bool，判断字符串中的括号是否平衡。支持 ()、[]、{} 三种括号。空字符串视为平衡。",
                        "points": 35,
                        "order_index": 5,
                        "starter_code": "def balanced_brackets(s: str) -> bool:\n    # 判断括号是否平衡\n    pass\n",
                        "public_cases": [
                            {"args": ["()"], "expected": True},
                            {"args": ["([{}])"], "expected": True},
                            {"args": ["([)]"], "expected": False},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    assert balanced_brackets('') == True\n"
                            "    assert balanced_brackets('(') == False\n"
                            "    assert balanced_brackets('(]') == False\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "active",
                    },
                ],
            },
        ],
    },
    {
        "title": "[验收] 数据分析与机器学习入门",
        "description": (
            "本课程介绍数据分析与机器学习的基础概念，涵盖数据清洗、"
            "NumPy/Pandas 基础操作以及模型训练与评估的核心方法。"
        ),
        "chapters": [
            {
                "title": "数据获取与清洗",
                "order_index": 0,
                "lessons": [
                    {
                        "title": "缺失值与异常值",
                        "content_type": "markdown",
                        "content": (
                            "# 缺失值与异常值\n\n"
                            "## 学习目标\n\n"
                            "- 识别数据集中的缺失值与异常值\n"
                            "- 掌握缺失值填充和异常值处理策略\n"
                            "- 理解不同处理方式对分析结果的影响\n\n"
                            "## 核心知识\n\n"
                            "### 缺失值类型\n"
                            "- MCAR（完全随机缺失）\n"
                            "- MAR（随机缺失）\n"
                            "- MNAR（非随机缺失）\n\n"
                            "### 处理策略\n"
                            "- 删除含缺失值的行/列\n"
                            "- 均值/中位数/众数填充\n"
                            "- 前向/后向填充\n"
                            "- 使用模型预测缺失值\n\n"
                            "## 示例\n\n"
                            "使用 Python 识别和填充缺失值。\n\n"
                            "## 练习\n\n"
                            "1. 加载含缺失值的数据集并统计缺失比例\n"
                            "2. 分别用不同策略填充并对比效果\n"
                            "3. 编写异常值检测函数"
                        ),
                    },
                    {
                        "title": "CSV 数据清洗流程",
                        "content_type": "markdown",
                        "content": (
                            "# CSV 数据清洗流程\n\n"
                            "## 学习目标\n\n"
                            "- 掌握 CSV 文件的完整清洗流程\n"
                            "- 能够编写可复用的清洗函数\n"
                            "- 理解数据质量检查清单\n\n"
                            "## 核心知识\n\n"
                            "### 标准清洗流程\n"
                            "1. 加载数据并检查基本信息\n"
                            "2. 处理列名（去空格、统一大小写、替换特殊字符）\n"
                            "3. 处理缺失值\n"
                            "4. 处理重复行\n"
                            "5. 类型转换与校验\n"
                            "6. 异常值检测\n\n"
                            "## 示例\n\n"
                            "完整的 CSV 清洗 pipeline 实现。\n\n"
                            "## 练习\n\n"
                            "1. 编写一个通用的 CSV 清洗函数\n"
                            "2. 添加数据质量报告功能\n"
                            "3. 处理编码问题（UTF-8 BOM 等）"
                        ),
                    },
                ],
            },
            {
                "title": "NumPy 与 Pandas",
                "order_index": 1,
                "lessons": [
                    {
                        "title": "向量化计算",
                        "content_type": "markdown",
                        "content": (
                            "# 向量化计算\n\n"
                            "## 学习目标\n\n"
                            "- 理解向量化与循环的本质区别\n"
                            "- 掌握 NumPy 数组的基本操作\n"
                            "- 能够将循环代码改写为向量化操作\n\n"
                            "## 核心知识\n\n"
                            "### 为什么向量化更快\n"
                            "- 底层 C/Fortran 实现\n"
                            "- CPU 向量指令（SIMD）\n"
                            "- 避免 Python 解释器循环开销\n\n"
                            "### 常见向量化操作\n"
                            "- 逐元素运算（+、-、*、/）\n"
                            "- 广播（broadcasting）\n"
                            "- 聚合（sum、mean、std）\n"
                            "- 布尔索引\n\n"
                            "## 示例\n\n"
                            "对比纯 Python 循环与 NumPy 向量化的性能差异。\n\n"
                            "## 练习\n\n"
                            "1. 将 Python 循环实现的均值计算改为 NumPy 实现\n"
                            "2. 使用广播机制实现矩阵运算\n"
                            "3. 基准测试并分析性能提升倍数"
                        ),
                    },
                    {
                        "title": "分组聚合与透视表",
                        "content_type": "markdown",
                        "content": (
                            "# 分组聚合与透视表\n\n"
                            "## 学习目标\n\n"
                            "- 掌握 Pandas groupby 操作\n"
                            "- 理解 pivot_table 的用法\n"
                            "- 能够进行多维度数据分析\n\n"
                            "## 核心知识\n\n"
                            "### groupby 的 split-apply-combine\n"
                            "1. Split：按键将数据分组\n"
                            "2. Apply：对每组应用函数\n"
                            "3. Combine：将结果组合\n\n"
                            "### pivot_table 参数\n"
                            "- index：行索引\n"
                            "- columns：列索引\n"
                            "- values：聚合值\n"
                            "- aggfunc：聚合函数\n\n"
                            "## 示例\n\n"
                            "使用 Pandas 进行销售数据的多维分析。\n\n"
                            "## 练习\n\n"
                            "1. 使用 groupby 计算各部门平均薪资\n"
                            "2. 创建透视表分析产品销售趋势\n"
                            "3. 实现自定义聚合函数"
                        ),
                    },
                ],
            },
            {
                "title": "模型训练与评估",
                "order_index": 2,
                "lessons": [
                    {
                        "title": "训练集、验证集与测试集",
                        "content_type": "markdown",
                        "content": (
                            "# 训练集、验证集与测试集\n\n"
                            "## 学习目标\n\n"
                            "- 理解数据划分的重要性\n"
                            "- 掌握随机划分与分层划分\n"
                            "- 避免数据泄露\n\n"
                            "## 核心知识\n\n"
                            "### 典型划分比例\n"
                            "- 小数据集：60/20/20\n"
                            "- 大数据集：98/1/1\n"
                            "- 交叉验证：K-Fold\n\n"
                            "### 数据泄露陷阱\n"
                            "- 先标准化再划分\n"
                            "- 在划分前进行特征选择\n"
                            "- 测试集参与了训练决策\n\n"
                            "## 示例\n\n"
                            "使用 sklearn train_test_split 进行数据划分。\n\n"
                            "## 练习\n\n"
                            "1. 实现分层抽样划分函数\n"
                            "2. 比较随机划分与分层划分的标签分布\n"
                            "3. 编写数据泄露检测清单"
                        ),
                    },
                    {
                        "title": "分类指标与混淆矩阵",
                        "content_type": "markdown",
                        "content": (
                            "# 分类指标与混淆矩阵\n\n"
                            "## 学习目标\n\n"
                            "- 理解混淆矩阵的四个基本元素\n"
                            "- 掌握精确率、召回率、F1 的计算\n"
                            "- 能够根据场景选择合适的评估指标\n\n"
                            "## 核心知识\n\n"
                            "### 混淆矩阵\n"
                            "| | 预测正 | 预测负 |\n"
                            "|------|-------|-------|\n"
                            "| 实际正 | TP | FN |\n"
                            "| 实际负 | FP | TN |\n\n"
                            "### 指标公式\n"
                            "- 精确率 = TP / (TP + FP)\n"
                            "- 召回率 = TP / (TP + FN)\n"
                            "- F1 = 2 * P * R / (P + R)\n"
                            "- 准确率 = (TP + TN) / Total\n\n"
                            "## 示例\n\n"
                            "手算混淆矩阵指标并验证。\n\n"
                            "## 练习\n\n"
                            "1. 给定混淆矩阵，计算各指标\n"
                            "2. 分析精确率与召回率的权衡\n"
                            "3. 实现多分类的宏平均与微平均"
                        ),
                    },
                ],
            },
        ],
        "assignments": [
            {
                "title": "[验收] 数据处理综合练习",
                "description": "数据清洗与基础统计编程练习",
                "questions": [
                    {
                        "title": "清洗数值序列",
                        "description": "编写函数 clean_numbers(values: list) -> list[float]，清洗包含缺失值（None）和异常字符串的数值序列。将 None 替换为 0.0，能转为数字的字符串转为 float，无法转换的值跳过。",
                        "function_name": "clean_numbers",
                        "signature": "def clean_numbers(values: list) -> list[float]",
                        "starter_code": "def clean_numbers(values: list) -> list[float]:\\n    # 清洗数值序列：跳过异常值，填充缺失值\\n    pass\\n",
                        "public_cases": [
                            {"args": [[1, None, 3]], "expected": [1.0, 0.0, 3.0]},
                            {"args": [["1.5", None, 2.0]], "expected": [1.5, 0.0, 2.0]},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    assert clean_numbers([]) == []\n"
                            "    assert clean_numbers([None]) == [0.0]\n"
                            "    assert clean_numbers(['abc', 1]) == [1.0]\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "legacy",
                    },
                    {
                        "title": "分组平均值",
                        "description": "编写函数 group_average(data: list[dict], group_key: str, value_key: str) -> dict，按 group_key 分组计算 value_key 的平均值，结果保留两位小数。",
                        "function_name": "group_average",
                        "signature": "def group_average(data: list[dict], group_key: str, value_key: str) -> dict",
                        "starter_code": "def group_average(data: list[dict], group_key: str, value_key: str) -> dict:\n    # 按指定键分组计算平均值\n    pass\n",
                        "public_cases": [
                            {"args": [[{"dept": "A", "score": 80}, {"dept": "A", "score": 90}, {"dept": "B", "score": 70}], "dept", "score"], "expected": {"A": 85.0, "B": 70.0}},
                            {"args": [[], "x", "y"], "expected": {}},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            '    d = [{"cat": "x", "v": 10.0}]\n'
                            "    assert group_average(d, 'cat', 'v') == {'x': 10.0}\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "shadow",
                    },
                    {
                        "title": "混淆矩阵指标",
                        "description": "编写函数 confusion_metrics(tp: int, fp: int, fn: int, tn: int) -> dict，返回包含 accuracy、precision、recall、f1 的字典，值保留四位小数。分母为零时对应指标为 0.0。",
                        "function_name": "confusion_metrics",
                        "signature": "def confusion_metrics(tp: int, fp: int, fn: int, tn: int) -> dict",
                        "starter_code": "def confusion_metrics(tp: int, fp: int, fn: int, tn: int) -> dict:\n    # 计算分类评估指标\n    pass\n",
                        "public_cases": [
                            {"args": [50, 10, 5, 35], "expected": {"accuracy": 0.85, "precision": 0.8333, "recall": 0.9091, "f1": 0.8696}},
                            {"args": [0, 0, 0, 100], "expected": {"accuracy": 1.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    r = confusion_metrics(1, 0, 0, 0)\n"
                            "    assert r['accuracy'] == 1.0\n"
                            "    assert r['precision'] == 1.0\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "active",
                    },
                ],
            },
        ],
        "exams": [
            {
                "title": "[验收] 数据分析综合测验",
                "duration_minutes": 90,
                "start_at": EXAM_START.isoformat(),
                "end_at": EXAM_END.isoformat(),
                "questions": [
                    {
                        "question_type": "single_choice",
                        "prompt": "Pandas 中 groupby 操作的核心范式是？",
                        "options": {"A": "map-reduce", "B": "split-apply-combine", "C": "filter-transform", "D": "select-project"},
                        "correct_answer": {"correct": ["B"]},
                        "points": 5,
                        "order_index": 0,
                    },
                    {
                        "question_type": "single_choice",
                        "prompt": "以下哪个指标最适合评估不平衡数据集的分类性能？",
                        "options": {"A": "准确率 (Accuracy)", "B": "F1 分数", "C": "均方误差 (MSE)", "D": "R² 分数"},
                        "correct_answer": {"correct": ["B"]},
                        "points": 5,
                        "order_index": 1,
                    },
                    {
                        "question_type": "multi_choice",
                        "prompt": "以下哪些属于数据泄露？（多选）",
                        "options": {"A": "在划分训练/测试集之前对全部数据进行标准化", "B": "用训练集的均值和标准差对测试集进行标准化", "C": "使用交叉验证选择模型参数", "D": "在划分前进行特征选择"},
                        "correct_answer": {"correct": ["A", "D"]},
                        "points": 10,
                        "order_index": 2,
                    },
                    {
                        "question_type": "multi_choice",
                        "prompt": "关于 NumPy 向量化操作，以下哪些描述是正确的？（多选）",
                        "options": {"A": "向量化操作比纯 Python 循环快", "B": "NumPy 底层使用 C 实现", "C": "广播机制允许不同形状数组间的运算", "D": "向量化操作不能用布尔索引"},
                        "correct_answer": {"correct": ["A", "B", "C"]},
                        "points": 10,
                        "order_index": 3,
                    },
                    {
                        "question_type": "code",
                        "prompt": "编写函数 min_max_scale(values: list[float]) -> list[float]，将数据缩放到 [0, 1] 区间。公式：(x - min) / (max - min)。所有值相同时返回全 0.5 的列表。",
                        "points": 35,
                        "order_index": 4,
                        "starter_code": "def min_max_scale(values: list[float]) -> list[float]:\n    # Min-Max 归一化到 [0, 1]\n    pass\n",
                        "public_cases": [
                            {"args": [[1.0, 5.0, 10.0]], "expected": [0.0, 0.4444]},
                            {"args": [[5.0, 5.0]], "expected": [0.5, 0.5]},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    assert min_max_scale([]) == []\n"
                            "    r = min_max_scale([0.0, 10.0])\n"
                            "    assert r == [0.0, 1.0]\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "legacy",
                    },
                    {
                        "question_type": "code",
                        "prompt": "编写函数 train_test_split_indices(n: int, test_ratio: float, seed: int = 42) -> tuple[list[int], list[int]]，将 [0, n) 的索引随机划分为训练集和测试集。使用 random.seed(seed) 保证可复现。",
                        "points": 35,
                        "order_index": 5,
                        "starter_code": "def train_test_split_indices(n: int, test_ratio: float, seed: int = 42) -> tuple[list[int], list[int]]:\n    # 随机划分训练/测试集索引\n    pass\n",
                        "public_cases": [
                            {"args": [10, 0.2, 42], "expected": None},
                        ],
                        "hidden_tests": (
                            "def test_hidden():\n"
                            "    train, test = train_test_split_indices(10, 0.2, 42)\n"
                            "    assert len(test) == 2\n"
                            "    assert len(train) == 8\n"
                            "    assert set(train) | set(test) == set(range(10))\n"
                            "    assert not set(train) & set(test)\n"
                        ),
                        "time_limit_ms": 5000,
                        "memory_limit_mb": 128,
                        "grading_mode": "shadow",
                    },
                ],
            },
        ],
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# 代表性提交数据
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_SUBMISSIONS: list[dict[str, Any]] = [
    {
        "student": "accept_student_a",
        "course_title": "[验收] Python 算法与工程实践",
        "assignment_title": "[验收] 作业一 Python 基础",
        "question_title": "规范化姓名",
        "code": (
            "def normalize_name(name: str) -> str:\n"
            '    """规范化姓名：去除首尾空白，将每个单词首字母大写"""\n'
            "    name = name.strip()\n"
            "    if not name:\n"
            '        return ""\n'
            "    return ' '.join(word.capitalize() for word in name.split())\n"
        ),
    },
    {
        "student": "accept_student_a",
        "course_title": "[验收] Python 算法与工程实践",
        "assignment_title": "[验收] 作业一 Python 基础",
        "question_title": "成绩摘要",
        "code": (
            "def summarize_scores(scores: list[float]) -> dict:\n"
            '    """统计成绩摘要信息"""\n'
            "    if not scores:\n"
            "        return {'min': None, 'max': None, 'avg': 0.0, 'count': 0}\n"
            "    return {\n"
            "        'min': min(scores),\n"
            "        'max': max(scores),\n"
            "        'avg': round(sum(scores) / len(scores), 2),\n"
            "        'count': len(scores),\n"
            "    }\n"
        ),
    },
    {
        "student": "accept_student_b",
        "course_title": "[验收] Python 算法与工程实践",
        "assignment_title": "[验收] 作业一 Python 基础",
        "question_title": "安全除法",
        "code": (
            "def safe_divide(a: float, b: float) -> float:\n"
            "    if b == 0:\n"
            "        return 0.0  # 错误：应该抛出 ValueError\n"
            "    return a / b\n"
        ),
    },
    {
        "student": "accept_student_b",
        "course_title": "[验收] Python 算法与工程实践",
        "assignment_title": "[验收] 作业一 Python 基础",
        "question_title": "成绩摘要",
        "code": (
            "def summarize_scores(scores: list[float]) -> dict:\n"
            '    """统计成绩摘要信息"""\n'
            "    return {\n"
            "        'min': min(scores),  # 空列表会崩溃\n"
            "        'max': max(scores),\n"
            "        'avg': sum(scores) / len(scores),  # 没取两位小数\n"
            "        'count': len(scores),\n"
            "    }\n"
        ),
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# API Client
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_PASSWORD = "Passw0rd!"


@dataclass
class SeedStats:
    """种子脚本运行统计"""
    created: int = 0
    reused: int = 0

    def inc_created(self):
        self.created += 1

    def inc_reused(self):
        self.reused += 1


class ApiClient:
    """封装 /api/v1 的 HTTP 客户端，带 Bearer Token 认证"""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token: str | None = None
        self._client = httpx.Client(timeout=httpx.Timeout(timeout))

    def login(self, username: str, password: str) -> dict:
        """登录并保存 token，返回用户信息"""
        resp = self._client.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password},
        )
        if resp.status_code != 200:
            raise SeedError(f"登录失败 ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        self.token = data["access_token"]
        self._user_id = data["user"]["id"]  # type: ignore[attr-defined]
        return data["user"]

    def _headers(self) -> dict:
        if not self.token:
            raise SeedError("未登录，请先调用 login()")
        return {"Authorization": f"Bearer {self.token}"}

    def _safe(self, resp: httpx.Response, action: str) -> dict:
        """检查响应状态，4xx/5xx 抛出 SeedError（不泄露 token）"""
        if resp.status_code < 400:
            return resp.json() if resp.content else {}
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            detail = resp.text[:200]
        raise SeedError(f"{action} 失败 ({resp.status_code}): {detail}")

    def get(self, path: str, **params) -> dict:
        resp = self._client.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=params,
        )
        return self._safe(resp, f"GET {path}")

    def post(self, path: str, json_data: dict | None = None, timeout: int | None = None) -> dict:
        """POST 请求，可覆盖超时"""
        kw = {"headers": self._headers()}
        if json_data is not None:
            kw["json"] = json_data
        if timeout is not None:
            kw["timeout"] = httpx.Timeout(timeout)
        resp = self._client.post(f"{self.base_url}{path}", **kw)  # type: ignore[arg-type]
        return self._safe(resp, f"POST {path}")

    def patch(self, path: str, json_data: dict, timeout: int | None = None) -> dict:
        kw = {"headers": self._headers(), "json": json_data}
        if timeout is not None:
            kw["timeout"] = httpx.Timeout(timeout)
        resp = self._client.patch(f"{self.base_url}{path}", **kw)
        return self._safe(resp, f"PATCH {path}")

    def paginated_list(self, path: str, **params) -> list[dict]:
        """获取分页列表，自动翻页收集全部条目"""
        all_items: list[dict] = []
        page = 1
        while True:
            p = {**params, "page": page, "page_size": 100}
            data = self.get(path, **p)
            items = data.get("items", [])
            all_items.extend(items)
            if len(all_items) >= data.get("total", 0):
                break
            page += 1
        return all_items

    def close(self):
        self._client.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 账号保障
# ═══════════════════════════════════════════════════════════════════════════════


def ensure_students(client: ApiClient, admin_username: str, admin_password: str, stats: SeedStats):
    """管理员登录后确保两个验收学生存在且凭据正确"""
    client.login(admin_username, admin_password)
    existing_users = client.paginated_list("/users")

    for stu in DEMO_STUDENTS:
        found = find_exact(existing_users, "username", stu["username"])
        if found:
            # 确保角色和状态正确
            uid = found["id"]
            if found.get("role") != "student" or found.get("status") != "active":
                client.patch(f"/users/{uid}", {"role": "student", "status": "active"})
            client.patch(f"/users/{uid}/password", {"password": DEFAULT_PASSWORD})
            stats.inc_reused()
        else:
            client.post("/users", {
                "username": stu["username"],
                "password": DEFAULT_PASSWORD,
                "real_name": stu["real_name"],
                "role": "student",
                "status": "active",
            })
            stats.inc_created()

    # 分别登录两个学生确认凭据
    for stu in DEMO_STUDENTS:
        sc = ApiClient(client.base_url)
        try:
            sc.login(stu["username"], DEFAULT_PASSWORD)
        finally:
            sc.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 课程、章节与课时保障
# ═══════════════════════════════════════════════════════════════════════════════


def ensure_course_structure(
    client: ApiClient,
    course_data: dict,
    stats: SeedStats,
) -> int:
    """确保一门课程的完整结构存在，返回课程 ID"""
    # 查询课程
    all_courses = client.paginated_list("/courses")
    course = find_exact(all_courses, "title", course_data["title"])

    if course:
        if course.get("teacher_id") != client._teacher_id:  # type: ignore[attr-defined]
            raise SeedError(
                f"课程 '{course_data['title']}' 不属于当前教师 "
                f"(teacher_id={course.get('teacher_id')})"
            )
        course_id = course["id"]
        stats.inc_reused()
    else:
        created = client.post("/courses", {
            "title": course_data["title"],
            "description": course_data.get("description", ""),
            "status": "draft",
        })
        course_id = created["id"]
        stats.inc_created()

    # 获取已有章节
    existing_chapters = client.paginated_list(f"/courses/{course_id}/chapters")

    for ch_data in course_data["chapters"]:
        ch = find_exact(existing_chapters, "title", ch_data["title"])
        if ch:
            ch_id = ch["id"]
            stats.inc_reused()
        else:
            created_ch = client.post(f"/courses/{course_id}/chapters", {
                "title": ch_data["title"],
                "order_index": ch_data["order_index"],
            })
            ch_id = created_ch["id"]
            stats.inc_created()

        # 重新获取该章节（含课时）
        all_chapters = client.paginated_list(f"/courses/{course_id}/chapters")
        chapter = find_exact(all_chapters, "id", ch_id)
        existing_lessons = (chapter or {}).get("lessons", [])

        for les_data in ch_data["lessons"]:
            les = find_exact(existing_lessons, "title", les_data["title"])
            if les:
                stats.inc_reused()
                # 如 API 支持更新课时的 content，则补齐（仅限验收脚本拥有的课时）
                try:
                    client.patch(f"/lessons/{les['id']}", {
                        "title": les_data["title"],
                        "content_type": les_data.get("content_type", "markdown"),
                        "content": les_data.get("content", ""),
                        "order_index": 0,
                    })
                except SeedError:
                    pass  # 内容不可覆盖时跳过
            else:
                client.post(f"/chapters/{ch_id}/lessons", {
                    "title": les_data["title"],
                    "content_type": les_data.get("content_type", "markdown"),
                    "content": les_data.get("content", ""),
                    "order_index": 0,
                })
                stats.inc_created()

    # 发布课程
    if course is None or course.get("status") != "published":
        client.patch(f"/courses/{course_id}", {"status": "published"})

    return course_id


def ensure_enrollments(client: ApiClient, course_id: int, stats: SeedStats):
    """确保两名验收学生选课"""
    for stu in DEMO_STUDENTS:
        sc = ApiClient(client.base_url)
        try:
            sc.login(stu["username"], DEFAULT_PASSWORD)
            try:
                sc.post(f"/courses/{course_id}/enroll")
                stats.inc_created()
            except SeedError as e:
                if "409" in str(e) or "已选" in str(e) or "enrolled" in str(e).lower():
                    # 确认确实已选课
                    sc.get(f"/courses/{course_id}")
                    stats.inc_reused()
                else:
                    raise
        finally:
            sc.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 作业与题目保障
# ═══════════════════════════════════════════════════════════════════════════════


def _retry_publish(client: ApiClient, path: str, *, is_post: bool = True, timeout: int = 180, max_retries: int = 3, json_data: dict | None = None):
    """带重试的发布调用，处理 AI Rubric 瞬时故障"""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            if is_post:
                return client.post(path, timeout=timeout)
            else:
                return client.patch(path, json_data or {}, timeout=timeout)
        except SeedError as e:
            last_err = e
            if attempt < max_retries and ("503" in str(e) or "AI_RUBRIC" in str(e) or "Rubric" in str(e)):
                wait = 2 ** attempt
                print(f"  发布重试 {attempt}/{max_retries}（{wait}s 后）: {e}")
                time.sleep(wait)
            else:
                raise
    raise last_err  # type: ignore[misc]


def ensure_assignments(
    client: ApiClient,
    course_id: int,
    course_data: dict,
    stats: SeedStats,
    publish_timeout: int = 180,
) -> list[int]:
    """确保作业及代码题存在并发布，返回作业 ID 列表"""
    assignment_ids: list[int] = []
    existing_assignments = client.paginated_list("/assignments", course_id=course_id)

    for asgn_data in course_data.get("assignments", []):
        asgn = find_exact(existing_assignments, "title", asgn_data["title"])
        if asgn:
            asgn_id = asgn["id"]
            stats.inc_reused()
        else:
            created = client.post("/assignments", {
                "course_id": course_id,
                "title": asgn_data["title"],
                "description": asgn_data.get("description", ""),
                "status": "draft",
            })
            asgn_id = created["id"]
            stats.inc_created()

        # 确保题目
        existing_qs = client.paginated_list(f"/assignments/{asgn_id}/questions")
        for q_data in asgn_data.get("questions", []):
            q = find_exact(existing_qs, "title", q_data["title"])
            if q:
                stats.inc_reused()
            else:
                client.post(f"/assignments/{asgn_id}/questions", {
                    "title": q_data["title"],
                    "description": q_data.get("description", ""),
                    "function_name": q_data["function_name"],
                    "signature": q_data.get("signature", ""),
                    "starter_code": q_data.get("starter_code", ""),
                    "public_cases": q_data.get("public_cases", []),
                    "hidden_tests": q_data.get("hidden_tests", ""),
                    "time_limit_ms": q_data.get("time_limit_ms", 5000),
                    "memory_limit_mb": q_data.get("memory_limit_mb", 128),
                    "grading_mode": q_data.get("grading_mode", "legacy"),
                })
                stats.inc_created()

        # 发布（含 AI rubric 生成，可能需要较长超时与重试）
        current = asgn or client.get(f"/assignments/{asgn_id}")
        if current.get("status") != "published":
            if current.get("status") != "draft":
                client.patch(f"/assignments/{asgn_id}", {"status": "draft"})
            _retry_publish(client, f"/assignments/{asgn_id}/publish", timeout=publish_timeout)

        assignment_ids.append(asgn_id)

    return assignment_ids


# ═══════════════════════════════════════════════════════════════════════════════
# 考试与题目保障
# ═══════════════════════════════════════════════════════════════════════════════


def ensure_exams(
    client: ApiClient,
    course_id: int,
    course_data: dict,
    stats: SeedStats,
    publish_timeout: int = 180,
) -> list[int]:
    """确保考试及题目存在并发布，返回考试 ID 列表"""
    exam_ids: list[int] = []
    existing_exams = client.paginated_list("/exams")

    for exam_data in course_data.get("exams", []):
        exam = find_exact(existing_exams, "title", exam_data["title"])
        if exam:
            exam_id = exam["id"]
            stats.inc_reused()
        else:
            created = client.post("/exams", {
                "course_id": course_id,
                "title": exam_data["title"],
                "duration_minutes": exam_data.get("duration_minutes", 90),
                "start_at": exam_data.get("start_at"),
                "end_at": exam_data.get("end_at"),
            })
            exam_id = created["id"]
            stats.inc_created()

        # 确保题目
        existing_qs = client.paginated_list(f"/exams/{exam_id}/questions")
        for q_data in exam_data.get("questions", []):
            # 用 prompt 做精确查找（题目没有 title 字段的统一概念）
            q = find_exact(existing_qs, "prompt", q_data["prompt"])
            if q:
                stats.inc_reused()
            else:
                payload = {
                    "question_type": q_data["question_type"],
                    "prompt": q_data["prompt"],
                    "points": q_data.get("points", 1),
                    "order_index": q_data.get("order_index", 0),
                    "correct_answer": q_data.get("correct_answer", {}),
                }
                if q_data.get("options"):
                    payload["options"] = q_data["options"]
                if q_data.get("starter_code") is not None:
                    payload["starter_code"] = q_data["starter_code"]
                if q_data.get("public_cases") is not None:
                    payload["public_cases"] = q_data["public_cases"]
                if q_data.get("hidden_tests") is not None:
                    payload["hidden_tests"] = q_data["hidden_tests"]
                if q_data.get("time_limit_ms") is not None:
                    payload["time_limit_ms"] = q_data["time_limit_ms"]
                if q_data.get("memory_limit_mb") is not None:
                    payload["memory_limit_mb"] = q_data["memory_limit_mb"]
                if q_data.get("grading_mode") is not None:
                    payload["grading_mode"] = q_data["grading_mode"]
                client.post(f"/exams/{exam_id}/questions", payload)
                stats.inc_created()

        # 发布（AI rubric 生成需要较长超时与重试）
        current = exam or client.get(f"/exams/{exam_id}")
        if current.get("status") != "published":
            if current.get("status") != "draft":
                client.patch(f"/exams/{exam_id}", {"status": "draft"})
            _retry_publish(
                client,
                f"/exams/{exam_id}",
                is_post=False,
                timeout=publish_timeout,
                json_data={
                    "status": "published",
                    "start_at": exam_data.get("start_at"),
                    "end_at": exam_data.get("end_at"),
                },
            )

        exam_ids.append(exam_id)

    return exam_ids


# ═══════════════════════════════════════════════════════════════════════════════
# 代表性提交与轮询
# ═══════════════════════════════════════════════════════════════════════════════


def _lookup_question_id(
    client: ApiClient,
    course_title: str,
    assignment_title: str,
    question_title: str,
) -> int | None:
    """通过课程→作业→题目链查找题目 ID"""
    courses = client.paginated_list("/courses")
    course = find_exact(courses, "title", course_title)
    if not course:
        return None
    assignments = client.paginated_list("/assignments", course_id=course["id"])
    asgn = find_exact(assignments, "title", assignment_title)
    if not asgn:
        return None
    questions = client.paginated_list(f"/assignments/{asgn['id']}/questions")
    q = find_exact(questions, "title", question_title)
    return q["id"] if q else None


_TERMINAL_STATUSES = {"passed", "wrong_answer", "system_error"}


def ensure_submissions(
    client: ApiClient,
    stats: SeedStats,
    submission_timeout: int = 180,
) -> list[dict]:
    """创建代表性提交并轮询至终态"""
    results: list[dict] = []

    for sub_data in DEMO_SUBMISSIONS:
        student_username = sub_data["student"]
        # 以学生身份查找题目 ID
        sc = ApiClient(client.base_url)
        try:
            sc.login(student_username, DEFAULT_PASSWORD)
            q_id = _lookup_question_id(
                sc,
                sub_data["course_title"],
                sub_data["assignment_title"],
                sub_data["question_title"],
            )
            if q_id is None:
                results.append({
                    "student": student_username,
                    "question": sub_data["question_title"],
                    "status": "question_not_found",
                })
                continue

            # 检查是否已有提交
            existing_subs = sc.paginated_list("/judge/submissions")
            existing = [
                s for s in existing_subs
                if s.get("question_id") == q_id
                and s.get("student_id") == sc._user_id  # type: ignore[attr-defined]
            ]
            if existing:
                # 轮询现有提交到终态
                sub = existing[0]
                sub = _poll_submission(sc, sub["id"], submission_timeout)
                results.append({
                    "student": student_username,
                    "question": sub_data["question_title"],
                    "submission_id": sub["id"],
                    "status": sub.get("status"),
                    "reused": True,
                })
                stats.inc_reused()
                continue

            # 创建提交
            created = sc.post("/judge/submissions", {
                "question_id": q_id,
                "code": sub_data["code"],
            })
            stats.inc_created()
            sub = _poll_submission(sc, created["id"], submission_timeout)
            results.append({
                "student": student_username,
                "question": sub_data["question_title"],
                "submission_id": sub["id"],
                "status": sub.get("status"),
                "reused": False,
            })
        finally:
            sc.close()

    return results


def _poll_submission(client: ApiClient, submission_id: int, timeout: int) -> dict:
    """轮询提交至终态，超时抛出 SeedError"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sub = client.get(f"/judge/submissions/{submission_id}")
        status = sub.get("status", "")
        if status in _TERMINAL_STATUSES:
            return sub
        time.sleep(2)
    raise SeedError(
        f"提交 {submission_id} 在 {timeout}s 内未达到终态"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(description="DAI 验收演示数据脚本")
    parser.add_argument("--base-url", default="http://localhost:8080/api/v1")
    parser.add_argument("--admin-username", default="admin")
    parser.add_argument("--teacher-username", default="teacher")
    parser.add_argument("--submission-timeout", type=int, default=180)
    parser.add_argument("--skip-submissions", action="store_true")
    args = parser.parse_args()

    admin_password = os.environ.get("DAI_SEED_ADMIN_PASSWORD", DEFAULT_PASSWORD)
    teacher_password = os.environ.get("DAI_SEED_TEACHER_PASSWORD", DEFAULT_PASSWORD)

    stats = SeedStats()
    client = ApiClient(args.base_url)

    course_ids: list[int] = []
    assignment_ids: list[int] = []
    exam_ids: list[int] = []
    submission_results: list[dict] = []

    try:
        # 1. 保障学生账号
        ensure_students(client, args.admin_username, admin_password, stats)

        # 2. 教师登录，保障课程结构
        teacher_user = client.login(args.teacher_username, teacher_password)
        client._teacher_id = teacher_user["id"]  # type: ignore[attr-defined]

        for course_data in ACCEPTANCE_DATA:
            cid = ensure_course_structure(client, course_data, stats)
            course_ids.append(cid)

            # 3. 选课
            ensure_enrollments(client, cid, stats)

            # 4. 作业与考试
            aids = ensure_assignments(client, cid, course_data, stats, args.submission_timeout)
            assignment_ids.extend(aids)

            eids = ensure_exams(client, cid, course_data, stats, args.submission_timeout)
            exam_ids.extend(eids)

        # 5. 代表性提交
        if not args.skip_submissions:
            submission_results = ensure_submissions(client, stats, args.submission_timeout)

    except SeedError as e:
        print(f"\n[ERROR] {e}")
        return 1
    finally:
        client.close()

    # ── 摘要 ──
    print("\n" + "=" * 60)
    print("  验收数据脚本 — 执行摘要")
    print("=" * 60)
    print(f"  创建: {stats.created}  复用: {stats.reused}")
    print(f"  课程 ID: {', '.join(str(i) for i in course_ids)}")
    print(f"  作业 ID: {', '.join(str(i) for i in assignment_ids)}")
    print(f"  考试 ID: {', '.join(str(i) for i in exam_ids)}")
    print(f"  教师用户: {args.teacher_username}")
    print(f"  学生用户: accept_student_a, accept_student_b")
    print(f"  默认密码: {DEFAULT_PASSWORD}")
    print()
    for cid in course_ids:
        print(f"  课程管理: {args.base_url.rsplit('/api/', 1)[0]}/teacher/courses/{cid}/manage")
    print()
    if submission_results:
        print("  代表性提交:")
        fail_count = 0
        for r in submission_results:
            tag = "复用" if r.get("reused") else "新建"
            print(f"    [{tag}] {r['student']} / {r['question']} → {r['status']}")
            if r["status"] not in _TERMINAL_STATUSES:
                fail_count += 1
        if fail_count > 0:
            print(f"\n  警告: {fail_count} 个提交未达终态")
    print("=" * 60)

    return 0 if all(
        r.get("status") in _TERMINAL_STATUSES
        for r in submission_results
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
