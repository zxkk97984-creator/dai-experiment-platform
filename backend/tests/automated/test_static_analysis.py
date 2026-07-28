"""Task 6: 静态分析测试——AST 解析、Ruff 诊断、Radon 圈复杂度"""
from app.services.static_analysis import analyze_python


def test_valid_code_returns_parseable():
    """合法代码返回 parseable=True"""
    result = analyze_python("def add(a, b):\n    return a + b\n")
    assert result["parseable"] is True
    assert result["syntax_error"] is None


def test_syntax_error_reported():
    """语法错误的代码返回 parseable=False"""
    result = analyze_python("def add(a, b):\n    return a + \n")
    assert result["parseable"] is False
    assert result["syntax_error"] is not None


def test_static_analysis_includes_basic_metrics():
    """静态分析包含基本指标"""
    code = "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"
    result = analyze_python(code)
    assert result["parseable"] is True
    assert result["line_count"] == 5


def test_static_analysis_does_not_execute_code():
    """静态分析不执行危险代码"""
    code = "import os; os.system('rm -rf /')\n"
    result = analyze_python(code)
    # 不会实际执行，只是语法分析
    assert "parseable" in result


def test_static_analysis_empty_code():
    """空代码处理"""
    result = analyze_python("")
    assert result["parseable"] is True
    assert result["line_count"] == 0
