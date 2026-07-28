"""只读静态分析——AST、Ruff、Radon"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


def analyze_python(code: str) -> dict:
    """对 Python 代码进行只读静态分析——不执行代码"""
    lines = code.splitlines()
    line_count = len(lines)

    result = {
        "parseable": True,
        "syntax_error": None,
        "line_count": line_count,
        "diagnostics": [],
        "complexity": {},
    }

    # AST 解析
    try:
        tree = ast.parse(code)
        # 基本统计
        func_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
        max_nesting = _max_nesting(tree)
        result["function_count"] = func_count
        result["max_nesting"] = max_nesting
    except SyntaxError as exc:
        result["parseable"] = False
        result["syntax_error"] = str(exc)
        return result

    # Ruff 诊断（子进程，5 秒超时）
    try:
        ruff_result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--output-format", "json", "-"],
            input=code,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ruff_result.returncode in (0, 1):  # 0=clean, 1=issues found
            try:
                diagnostics = json_loads_limited(ruff_result.stdout, max_items=100)
                result["diagnostics"] = diagnostics
            except (ValueError, TypeError):
                result["diagnostics"] = []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        result["diagnostics"] = []

    # Radon 圈复杂度
    try:
        radon_result = subprocess.run(
            [sys.executable, "-m", "radon", "cc", "-j", "-"],
            input=code,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if radon_result.returncode == 0 and radon_result.stdout.strip():
            try:
                result["complexity"] = json_loads_limited(radon_result.stdout, max_items=50)
            except (ValueError, TypeError):
                result["complexity"] = {}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        result["complexity"] = {}

    return result


def _max_nesting(tree: ast.AST) -> int:
    """计算 AST 最大嵌套深度"""
    max_depth = 0

    def walk(node, depth=0):
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.For, ast.While, ast.If, ast.With, ast.Try, ast.ExceptHandler)):
                walk(child, depth + 1)
            else:
                walk(child, depth)

    walk(tree)
    return max_depth


def json_loads_limited(text: str, max_items: int = 100) -> list | dict:
    """受限 JSON 解析——截断超长结果"""
    import json
    data = json.loads(text)
    if isinstance(data, list) and len(data) > max_items:
        return data[:max_items]
    return data
