"""包名校验与 import 策略（Phase 1：服务层校验）

教学反馈层，不是安全边界——真正的隔离由 Docker 运行参数负责。

- 供应链输入校验：pip 包名 / 锁定版本 / import 名严格格式（拒绝注入）
- 学生代码静态 import 分析（AST）：import / from import / importlib 字面量
- classify_imports：IMPORT_NOT_ALLOWED（教学策略）与 IMPORT_NOT_INSTALLED（平台配置）区分
"""
from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from typing import Literal

from packaging.version import InvalidVersion, Version

from app.schemas.environments import ImportDiagnosticRead

# ═══════════════════════════════════════════════════════════════
# 供应链输入校验
# ═══════════════════════════════════════════════════════════════

_PIP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_VERSION_CHARS_RE = re.compile(r"^[A-Za-z0-9.+\-!]+$")
_IMPORT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")

_MAX_PIP_NAME = 128
_MAX_VERSION = 64
_MAX_IMPORT_NAME = 128


def normalize_pip_name(value: str) -> str:
    """校验并归一化 pip 包名，返回 PEP 503 canonical 形式。

    只允许字母、数字、点、下划线、短横线；长度 ≤128。
    归一化规则：小写，`-_.` 连续运行符归并为单个 `-`（PEP 503）。
    拒绝：换行、空白、URL、路径分隔、pip 参数（==、[]、; marker 等）。
    """
    if not isinstance(value, str) or not value:
        raise ValueError("pip 包名不能为空")
    if len(value) > _MAX_PIP_NAME:
        raise ValueError("pip 包名长度不能超过 128")
    if not _PIP_NAME_RE.match(value):
        raise ValueError("pip 包名只允许字母、数字、点、下划线、短横线")
    return re.sub(r"[-_.]+", "-", value).lower()


def validate_locked_version(value: str) -> str:
    """校验锁定版本必须是单个精确 PEP 440 版本，返回原字符串。

    拒绝：范围/通配符（>=、~=、==1.*、!=）、URL、路径、extras、marker、换行、空白。
    """
    if not isinstance(value, str) or not value:
        raise ValueError("锁定版本不能为空")
    if len(value) > _MAX_VERSION:
        raise ValueError("锁定版本长度不能超过 64")
    if not _VERSION_CHARS_RE.match(value):
        raise ValueError("锁定版本必须为单个精确 PEP 440 版本")
    try:
        Version(value)
    except InvalidVersion:
        raise ValueError("锁定版本必须为单个精确 PEP 440 版本") from None
    return value


def normalize_import_name(value: str) -> str:
    """校验 import 名必须是合法 Python dotted identifier，归一化为顶级模块名。

    例：sklearn.metrics → sklearn（import 名统一比较顶级模块）。
    """
    if not isinstance(value, str) or not value:
        raise ValueError("import 名不能为空")
    if len(value) > _MAX_IMPORT_NAME:
        raise ValueError("import 名长度不能超过 128")
    if not _IMPORT_NAME_RE.match(value):
        raise ValueError("import 名必须是合法 Python 模块名")
    return value.split(".")[0]


def validate_import_names(values: list[str]) -> list[str]:
    """校验一组 import 名：逐个归一化、去重、排序，返回稳定列表。"""
    if not isinstance(values, list):
        raise ValueError("import 名必须是数组")
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        norm = normalize_import_name(v)
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return sorted(out)


# ═══════════════════════════════════════════════════════════════
# import 策略
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ImportPolicy:
    """作业/实验的 import 教学策略（三态：unrestricted / restricted / inherit）"""

    mode: Literal["unrestricted", "restricted", "inherit"]
    allowed_imports: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_mode(cls, mode: str, allowed_imports: list[str] | None = None) -> "ImportPolicy":
        if mode not in ("unrestricted", "restricted", "inherit"):
            raise ValueError(f"未知 import 策略模式: {mode}")
        return cls(mode=mode, allowed_imports=frozenset(validate_import_names(allowed_imports or [])))

    @property
    def restricted(self) -> bool:
        return self.mode == "restricted"


# Python 标准库 + 运行时基础模块——始终隐式允许，不要求教师逐个勾选
STDLIB_MODULES = frozenset(
    set(getattr(sys, "stdlib_module_names", set()))
    | {"builtins", "__main__", "__future__", "__builtin__", "site", "abc"}
)


def inspect_student_imports(source: str) -> set[str]:
    """静态分析学生代码中的 import（AST），返回归一化顶级模块名集合。

    - 支持 `import x`、`import x.y`、`from x import ...`、`importlib.import_module("x")`（仅字面量）
    - 语法错误返回空集——不伪装成 import 错误，交给判题/Kernel 原始输出
    - 只检查学生源代码，不检查 pytest、隐藏测试或第三方包内部 import
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:  # `from . import x` 无 module，跳过相对导入
                imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "import_module"
                and isinstance(func.value, ast.Name)
                and func.value.id == "importlib"
            ):
                # 仅识别字面量参数；不宣称可以阻止所有动态加载
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    imports.add(node.args[0].value.split(".")[0])
    return imports


def classify_imports(
    source: str,
    policy: ImportPolicy,
    installed_imports: set[str],
) -> list[ImportDiagnosticRead]:
    """对学生代码做 import 分类诊断。

    - restricted 且模块不在白名单：IMPORT_NOT_ALLOWED（标准库隐式允许）
    - 规则允许，但环境 manifest 没有该模块：IMPORT_NOT_INSTALLED（平台配置问题，不扣分）
    - 语法错误：返回空列表，不伪装成 import 错误
    """
    if not policy.restricted:
        return []
    modules = inspect_student_imports(source)
    diagnostics: list[ImportDiagnosticRead] = []
    for module in sorted(modules):
        if module in STDLIB_MODULES:
            continue
        if module not in policy.allowed_imports:
            diagnostics.append(
                ImportDiagnosticRead(
                    code="IMPORT_NOT_ALLOWED",
                    module=module,
                    message=f"{module} 未在本作业允许范围内",
                )
            )
        elif module not in installed_imports:
            diagnostics.append(
                ImportDiagnosticRead(
                    code="IMPORT_NOT_INSTALLED",
                    module=module,
                    message=f"本题允许使用 {module}，但当前运行环境未安装；这是平台配置问题，请联系教师",
                )
            )
    return diagnostics
