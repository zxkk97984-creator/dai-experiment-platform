"""import 策略与包名校验测试（Phase 1：服务层校验）

覆盖：
- pip 包名 / 锁定版本 / import 名的严格格式校验（拒绝注入）
- 学生代码 import 静态分析（AST）
- classify_imports 三态策略诊断（IMPORT_NOT_ALLOWED / IMPORT_NOT_INSTALLED）
"""
from __future__ import annotations

import pytest

from app.schemas.environments import ImportDiagnosticRead
from app.services.import_policy import (
    ImportPolicy,
    classify_imports,
    inspect_student_imports,
    normalize_import_name,
    normalize_pip_name,
    validate_import_names,
    validate_locked_version,
)


# ═══════════════════════════════════════════════════════════════
# normalize_pip_name
# ═══════════════════════════════════════════════════════════════

def test_pip_name_accepts_legal_names():
    assert normalize_pip_name("numpy") == "numpy"
    assert normalize_pip_name("scikit-learn") == "scikit-learn"
    assert normalize_pip_name("scikit_learn") == "scikit-learn"  # PEP 503 归一化
    assert normalize_pip_name("torch") == "torch"
    assert normalize_pip_name("numpy2") == "numpy2"
    assert normalize_pip_name("a.b-c_d") == "a-b-c-d"  # 运行符均归并为 -


def test_pip_name_rejects_injection():
    # 换行 / 空格 / URL / 路径 / pip 参数
    for bad in [
        "", " ", "numpy==1.0", "numpy>=1.0", "numpy[all]",
        "numpy\n--trusted-host evil", "numpy; os.system('x')",
        "https://evil.com/x", "numpy/../evil", "-e numpy",
        "numpy --extra-index-url https://evil.com",
        "a" * 129,  # 超长
        123,  # 非字符串
    ]:
        with pytest.raises(ValueError):
            normalize_pip_name(bad)


# ═══════════════════════════════════════════════════════════════
# validate_locked_version
# ═══════════════════════════════════════════════════════════════

def test_locked_version_accepts_exact_versions():
    assert validate_locked_version("8.3.4") == "8.3.4"
    assert validate_locked_version("2.6.0+cpu") == "2.6.0+cpu"  # local version
    assert validate_locked_version("1!2.0") == "1!2.0"  # epoch
    assert validate_locked_version("1.0.post1") == "1.0.post1"
    assert validate_locked_version("1.0.dev1") == "1.0.dev1"
    assert validate_locked_version("2.2.3") == "2.2.3"


def test_locked_version_rejects_ranges_wildcards_and_injection():
    for bad in [
        "", " ", ">=1.0", "~=1.0", "==1.*", "1.0.*", "1.0,<2.0", "!=1.0",
        "1.0; python_version<'3.8'",  # marker
        "1.0; os.system('x')",
        "1.0\n2.0",  # 换行注入
        "file:///etc/passwd",  # URL
        "1.0+file://x",
        "../1.0",
        "1.0-", "1.0 ",  # 尾部空白
        "a" * 65,  # 超长
        1.0,  # 非字符串
    ]:
        with pytest.raises(ValueError):
            validate_locked_version(bad)


# ═══════════════════════════════════════════════════════════════
# normalize_import_name
# ═══════════════════════════════════════════════════════════════

def test_import_name_normalizes_to_top_level():
    assert normalize_import_name("sklearn") == "sklearn"
    assert normalize_import_name("sklearn.metrics") == "sklearn"  # 顶级模块
    assert normalize_import_name("pandas.core.frame") == "pandas"
    assert normalize_import_name("_private_mod") == "_private_mod"


def test_import_name_rejects_illegal():
    for bad in ["", " ", "1numpy", "numpy-ml", "numpy/math", "numpy ml",
                "numpy..metrics", ".numpy", "a" * 129, None, 42]:
        with pytest.raises(ValueError):
            normalize_import_name(bad)


def test_validate_import_names_dedup_and_sort():
    assert validate_import_names(["sklearn.metrics", "numpy", "sklearn"]) == ["numpy", "sklearn"]
    assert validate_import_names([]) == []
    with pytest.raises(ValueError):
        validate_import_names(["numpy", "bad name"])


# ═══════════════════════════════════════════════════════════════
# inspect_student_imports（AST 静态分析）
# ═══════════════════════════════════════════════════════════════

def test_inspect_simple_imports():
    src = "import numpy\nimport sklearn.metrics as sm\nimport torch"
    assert inspect_student_imports(src) == {"numpy", "sklearn", "torch"}


def test_inspect_from_imports():
    src = "from numpy import array\nfrom pandas.core import frame"
    assert inspect_student_imports(src) == {"numpy", "pandas"}


def test_inspect_importlib_literal():
    src = 'import importlib\nmod = importlib.import_module("matplotlib")\n'
    assert inspect_student_imports(src) == {"importlib", "matplotlib"}


def test_inspect_dynamic_importlib_not_detected():
    # 非字面量参数不识别——不宣称能阻止所有动态加载
    src = 'import importlib\nmod = importlib.import_module(user_input)'
    assert inspect_student_imports(src) == {"importlib"}


def test_inspect_relative_and_defs_ignored():
    src = "from . import helper\ndef f():\n    return 1\n"
    assert inspect_student_imports(src) == set()


def test_inspect_syntax_error_returns_empty():
    # 语法错误不伪装成 import 错误——交给判题/Kernel 原始输出
    assert inspect_student_imports("def broken(:\n  pass") == set()


# ═══════════════════════════════════════════════════════════════
# classify_imports
# ═══════════════════════════════════════════════════════════════

INSTALLED = {"numpy", "pandas", "scipy", "sklearn", "matplotlib", "torch"}


def test_unrestricted_policy_returns_no_diagnostics():
    policy = ImportPolicy.from_mode("unrestricted")
    assert classify_imports("import numpy", policy, INSTALLED) == []


def test_restricted_import_not_allowed():
    policy = ImportPolicy.from_mode("restricted", ["numpy", "pandas"])
    diags = classify_imports("import numpy\nimport os\nimport sklearn", policy, INSTALLED)
    codes = {(d.code, d.module) for d in diags}
    assert ("IMPORT_NOT_ALLOWED", "sklearn") in codes
    assert ("IMPORT_NOT_ALLOWED", "os") not in codes  # 标准库隐式允许
    assert all(d.module != "numpy" for d in diags)  # 白名单内不诊断


def test_import_not_installed_but_allowed():
    # 白名单允许但环境未安装 → IMPORT_NOT_INSTALLED（平台配置问题，不扣分）
    policy = ImportPolicy.from_mode("restricted", ["numpy", "tensorflow"])
    diags = classify_imports("import tensorflow", policy, INSTALLED)
    assert len(diags) == 1
    assert diags[0].code == "IMPORT_NOT_INSTALLED"
    assert diags[0].module == "tensorflow"
    assert "未安装" in diags[0].message


def test_import_not_allowed_takes_precedence():
    # 既不在白名单也未安装 → 只报 IMPORT_NOT_ALLOWED
    policy = ImportPolicy.from_mode("restricted", ["numpy"])
    diags = classify_imports("import keras", policy, INSTALLED)
    assert [(d.code, d.module) for d in diags] == [("IMPORT_NOT_ALLOWED", "keras")]


def test_stdlib_never_diagnosed():
    policy = ImportPolicy.from_mode("restricted", [])
    diags = classify_imports("import math\nimport json\nimport collections", policy, set())
    assert diags == []


def test_installed_and_allowed_no_diagnostics():
    policy = ImportPolicy.from_mode("restricted", ["numpy", "pandas"])
    diags = classify_imports("import numpy as np\nfrom pandas import DataFrame", policy, INSTALLED)
    assert diags == []


def test_classify_syntax_error_returns_empty():
    policy = ImportPolicy.from_mode("restricted", ["numpy"])
    assert classify_imports("def broken(:", policy, INSTALLED) == []


def test_import_policy_invalid_mode_rejected():
    with pytest.raises(ValueError):
        ImportPolicy.from_mode("banana")
    with pytest.raises(ValueError):
        ImportPolicy.from_mode("restricted", ["bad name"])


def test_import_policy_normalizes_allowed_imports():
    policy = ImportPolicy.from_mode("restricted", ["sklearn.metrics", "numpy", "sklearn"])
    assert policy.allowed_imports == frozenset({"sklearn", "numpy"})


def test_diagnostic_read_has_required_fields():
    d = ImportDiagnosticRead(code="IMPORT_NOT_ALLOWED", module="numpy", message="numpy 未在本作业允许范围内")
    assert d.code == "IMPORT_NOT_ALLOWED"
    assert d.module == "numpy"
