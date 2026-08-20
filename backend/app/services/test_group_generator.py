"""AI 测试组生成服务——只生成、不保存

调用现有 DeepSeekClient 生成 F/R 测试组，经 8 步校验流水线后返回可回填
前端的 TestGroupsGenerateResponse。端点绝不写库：本服务不接收 Session、
不创建任何数据库记录。

hidden_tests 仅在 prompt 构造时使用，绝不写入响应或错误日志。
"""
from __future__ import annotations

import ast
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.schemas.ai_grading import (
    TestGroup,
    TestGroupsGenerateResponse,
    TestGroupsValidationSummary,
    check_test_groups_weights,
)
from app.services.ai_client import AIServiceError, DeepSeekClient
from app.services.ai_prompts import build_test_group_messages
from app.services.import_policy import STDLIB_MODULES, inspect_student_imports

# 生成测试的依赖白名单：Python 标准库 + 容器已有的第三方库
_ALLOWED_THIRD_PARTY_MODULES = frozenset({"pytest", "numpy", "pandas", "sklearn"})

# hidden_tests 发送给模型的 token 预算（字符）——超长时截断并在 warnings 告知
_HIDDEN_TESTS_BUDGET = 6000

# 危险 API：子进程、网络、文件系统破坏等（测试代码不得使用）
_DANGEROUS_MODULES = frozenset({
    "subprocess", "socket", "requests", "urllib", "http", "ftplib",
    "smtplib", "telnetlib", "pty", "webbrowser", "multiprocessing",
})
_DANGEROUS_FUNCS = frozenset({"eval", "exec"})
_DANGEROUS_ATTRS = frozenset({
    "system", "popen", "run", "call", "Popen", "check_call",
    "check_output", "getoutput", "connect", "sendall", "urlopen",
    "urlretrieve", "rmtree", "remove", "unlink", "startfile",
})


class TestGroupValidationError(RuntimeError):
    """生成结果经校验与修复后仍不合规——携带脱敏 issues（不含 hidden_tests）"""

    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


class PreflightUnavailableError(RuntimeError):
    """Docker 判题基础设施不可用，无法完成预检（不是生成结果不合规）"""


def generate_test_groups(
    client: DeepSeekClient,
    snapshot: dict[str, Any],
    settings: Settings,
    *,
    workdir: Path | str,
    host_workdir: Path | str | None = None,
    timeout_seconds: int | None = None,
    memory_limit_mb: int | None = None,
) -> TestGroupsGenerateResponse:
    """生成并校验测试组（最多两次模型调用：首次生成 + 一次修复）。

    校验（JSON/schema/语法/计分）或 Docker 预检失败时，携带脱敏问题列表
    进行一次修复生成；仍失败抛 TestGroupValidationError（issues 可展示给
    教师）。模型调用层面的异常（AIServiceError）直接向上抛，由端点映射。
    """
    warnings: list[str] = []
    hidden_tests = snapshot.get("hidden_tests") or ""
    if not hidden_tests.strip():
        warnings.append("题目无 hidden_tests，已按题干、签名与参考答案推导")
    elif len(hidden_tests) > _HIDDEN_TESTS_BUDGET:
        snapshot = dict(snapshot, hidden_tests=hidden_tests[:_HIDDEN_TESTS_BUDGET])
        warnings.append("hidden_tests 过长，已截断用于生成提示（不影响判题）")

    workdir = Path(workdir)
    host = Path(host_workdir) if host_workdir else workdir
    timeout = timeout_seconds or max(5, int(settings.judge_timeout_seconds))
    memory = memory_limit_mb or settings.judge_memory_limit_mb

    issues: list[str] = []
    for attempt in range(2):
        messages = build_test_group_messages(snapshot, fix_issues=(issues or None))
        try:
            # TASK-028：test_group_generation 预算 12000 max_tokens（含 reasoning token）
            payload = client.chat_json(messages, operation="test_group_generation")
        except AIServiceError as exc:
            if exc.code == "bad_json":
                # JSON 提取失败：携带提示进行一次修复生成
                issues = ["模型输出不是有效 JSON"]
                continue
            raise

        groups, attempt_issues = validate_generated_payload(payload)
        if not attempt_issues:
            preflight_issues = preflight_groups(
                groups,
                snapshot.get("reference_solution"),
                workdir, host, settings, timeout, memory,
            )
            if not preflight_issues:
                return _build_response(groups, warnings)
            attempt_issues = preflight_issues
        issues = attempt_issues

    raise TestGroupValidationError(issues)


def validate_generated_payload(payload: Any) -> tuple[list[TestGroup], list[str]]:
    """AI 输出校验流水线（Docker 预检之外的 1–6、8 步）。

    返回 (归一化后的 TestGroup 列表, issues)；issues 非空表示不合规，
    其内容只描述模型生成结果的问题，绝不包含 hidden_tests 原文。
    """
    issues: list[str] = []

    # 1. 提取 JSON，拒绝额外文本和未知字段
    if not isinstance(payload, dict):
        return [], ["模型输出不是 JSON 对象"]
    unknown = [k for k in payload if k != "test_groups"]
    if unknown:
        issues.append(f"响应包含未知字段: {', '.join(str(k) for k in unknown)}")
        return [], issues
    raw_groups = payload.get("test_groups")
    if not isinstance(raw_groups, list) or not raw_groups:
        return [], issues + ["响应缺少 test_groups 数组（必须至少一个测试组）"]

    # 2. 安全归一化（ID 大写/非法字符替换/冲突加后缀、去代码围栏）
    # 3. 构造现有 TestGroup，校验维度、分值范围、长度和非空测试
    used_ids: set[str] = set()
    groups: list[TestGroup] = []
    for idx, item in enumerate(raw_groups, 1):
        if not isinstance(item, dict):
            issues.append(f"第 {idx} 个测试组不是对象")
            continue
        try:
            group = TestGroup(
                id=_normalize_group_id(item.get("id", ""), used_ids),
                name=str(item.get("name", "")).strip() or f"测试组{idx}",
                dimension=str(item.get("dimension", "")).upper(),
                max_score=float(item.get("max_score", 0)),
                tests=_strip_code_fence(str(item.get("tests", ""))),
            )
        except (ValidationError, TypeError, ValueError) as exc:
            issues.append(f"第 {idx} 个测试组不合法: {_first_error_detail(exc)}")
            continue
        groups.append(group)

    if not groups:
        return [], issues or ["没有可用的测试组"]

    # 4. 分值按维度归一：F=60、R=10，保留相对权重，最后一组吸收小数误差
    try:
        groups = _rescale_scores(groups)
    except TestGroupValidationError as exc:
        return [], issues + exc.issues

    # 5. ID 唯一、F/R 均存在、各 1–2 组
    if len({g.id for g in groups}) != len(groups):
        issues.append("测试组 ID 必须唯一")
    f_count = sum(1 for g in groups if g.dimension == "F")
    r_count = sum(1 for g in groups if g.dimension == "R")
    if f_count == 0:
        issues.append("缺少 F 组")
    if r_count == 0:
        issues.append("缺少 R 组")
    if f_count > 2:
        issues.append(f"F 组数量应为 1–2，当前 {f_count} 个")
    if r_count > 2:
        issues.append(f"R 组数量应为 1–2，当前 {r_count} 个")

    # 6. ast 语法、导入依赖及危险 API
    for group in groups:
        code = group.tests
        try:
            ast.parse(code)
        except SyntaxError as exc:
            issues.append(f"{group.id}.tests 语法错误: 第 {exc.lineno or '?'} 行 {exc.msg}")
            continue
        for module in sorted(inspect_student_imports(code)):
            if module in STDLIB_MODULES or module in _ALLOWED_THIRD_PARTY_MODULES:
                continue
            issues.append(f"依赖 {module} 未安装或不在允许范围")
        issues.extend(
            f"{group.id}.tests {issue}" for issue in _check_dangerous_apis(code)
        )

    # 8. 复用与 AIQuestionConfigUpdate 相同的共享强校验，避免规则漂移
    if not issues:
        try:
            check_test_groups_weights(groups)
        except ValueError as exc:
            issues.append(str(exc))

    return groups, issues


def preflight_groups(
    groups: list[TestGroup],
    reference_solution: str | None,
    workdir: Path,
    host_workdir: Path,
    settings: Settings,
    timeout_seconds: int,
    memory_limit_mb: int,
) -> list[str]:
    """使用与判题一致的 Docker 镜像预检（流水线第 7 步）。

    - 有参考答案：以参考答案为 user_code 执行各组并要求全部通过；
    - 无参考答案：至少完成语法、导入与 pytest collection 检查。
    返回 issues 列表；空列表表示通过。Docker 基础设施不可用抛
    PreflightUnavailableError（属平台问题，不是生成结果不合规）。
    """
    from app.worker.judge_worker import _run_docker_pytest, run_test_groups

    workdir = Path(workdir).resolve()
    host = Path(host_workdir).resolve() if host_workdir else workdir
    issues: list[str] = []

    # Docker 挂载的是 host_workdir。若 host_workdir 与写入目录不同（生产 DoD 配置），
    # 必须把预检文件写到 host_workdir 下，否则容器内会看不到 test_group.py。
    try:
        host.mkdir(parents=True, exist_ok=True)
        run_dir = (
            Path(tempfile.mkdtemp(prefix="dai-testgen-preflight-", dir=host))
            if host != workdir else workdir
        )
    except OSError as exc:
        raise PreflightUnavailableError(
            f"判题工作目录不可写，无法完成测试组预检: {exc}"
        ) from exc

    try:
        if reference_solution and reference_solution.strip():
            result = run_test_groups(
                run_dir, run_dir, reference_solution,
                [g.model_dump() for g in groups],
                settings, timeout_seconds, memory_limit_mb,
            )
            for err in result["system_errors"]:
                if "Docker 执行异常" in err:
                    raise PreflightUnavailableError(
                        "判题服务不可用（Docker 未就绪），无法完成测试组预检"
                    )
                issues.append(err)
            for gid, counts in result["results"].items():
                if counts["passed"] <= 0 or counts["failed"] > 0 or counts["errors"] > 0:
                    issues.append(
                        f"测试组 {gid} 未通过参考答案预检"
                        f"（passed={counts['passed']}, failed={counts['failed']}, "
                        f"errors={counts['errors']}）"
                    )
            return issues

        # 无参考答案：pytest --collect-only 检查各组可收集性
        # 先写占位 user_code.py（空模块即可）：测试内容会自动补 `from user_code import *`，
        # 与判题路径（judge_worker.run_test_groups）一致，否则 collection 阶段 import 失败。
        (run_dir / "user_code.py").write_text("", encoding="utf-8")
        for group in groups:
            test_content = group.tests
            if "import user_code" not in test_content and "from user_code" not in test_content:
                test_content = f"from user_code import *\n\n{test_content}"
            (run_dir / "test_group.py").write_text(test_content, encoding="utf-8")
            try:
                stdout, stderr, returncode, _ = _run_docker_pytest(
                    run_dir, settings, timeout_seconds, memory_limit_mb,
                    test_filename="test_group.py", host_workdir=run_dir,
                    extra_args=["--collect-only"],
                )
            except FileNotFoundError:
                raise PreflightUnavailableError(
                    "判题服务不可用（Docker 未就绪），无法完成测试组预检"
                )
            if returncode != 0:
                tail = (stderr or stdout).strip().splitlines()[-1] if (stderr or stdout).strip() else "无输出"
                issues.append(f"测试组 {group.id} 无法被 pytest 收集: {tail[:200]}")

        return issues
    finally:
        if run_dir != workdir:
            shutil.rmtree(run_dir, ignore_errors=True)


# ── 内部辅助 ──


def _build_response(groups: list[TestGroup], warnings: list[str]) -> TestGroupsGenerateResponse:
    return TestGroupsGenerateResponse(
        test_groups=groups,
        validation=TestGroupsValidationSummary(
            f_total=round(sum(g.max_score for g in groups if g.dimension == "F"), 4),
            r_total=round(sum(g.max_score for g in groups if g.dimension == "R"), 4),
            group_count=len(groups),
            f_group_count=sum(1 for g in groups if g.dimension == "F"),
            r_group_count=sum(1 for g in groups if g.dimension == "R"),
        ),
        warnings=warnings,
        generation_id=uuid.uuid4().hex[:12],
    )


def _normalize_group_id(raw: Any, used: set[str]) -> str:
    """ID 安全归一化：大写、非法字符替换为下划线、以字母开头、冲突加后缀"""
    value = re.sub(r"[^A-Za-z0-9_]", "_", str(raw or "")).upper()
    if not value:
        value = "G"
    if not value[0].isalpha():
        value = "G_" + value
    value = value[:40]
    base = value
    n = 2
    while value in used:
        suffix = f"_{n}"
        value = base[: 40 - len(suffix)] + suffix
        n += 1
    used.add(value)
    return value


def _strip_code_fence(text: str) -> str:
    """去除模型可能输出的 Markdown 代码围栏"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _rescale_scores(groups: list[TestGroup]) -> list[TestGroup]:
    """按维度归一分值（F=60、R=10），保留相对权重，最后一组吸收小数误差"""
    scaled_by_id: dict[str, TestGroup] = {}
    for dim, target in (("F", 60.0), ("R", 10.0)):
        dim_groups = [g for g in groups if g.dimension == dim]
        if not dim_groups:
            continue  # 缺组由后续校验报告
        total_weight = sum(g.max_score for g in dim_groups)
        if total_weight <= 0:
            raise TestGroupValidationError([f"{dim} 组分值总和必须大于 0"])
        scaled: list[float] = []
        for g in dim_groups[:-1]:
            scaled.append(round(target * g.max_score / total_weight, 4))
        scaled.append(round(target - sum(scaled), 4))
        if any(v <= 0 for v in scaled):
            raise TestGroupValidationError([f"{dim} 组归一化后存在非正分值"])
        for g, v in zip(dim_groups, scaled):
            scaled_by_id[g.id] = g.model_copy(update={"max_score": v})
    return [scaled_by_id[g.id] for g in groups]


def _check_dangerous_apis(code: str) -> list[str]:
    """检查测试代码中的危险 API（子进程、网络、文件系统破坏、eval/exec）"""
    issues: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return issues  # 语法错误由独立检查报告
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in _DANGEROUS_FUNCS:
                issues.append(f"使用了危险调用 {func.id}")
            if func.id == "open" and _open_mode_contains_write(node):
                issues.append("使用了文件写入操作 open(..., 写模式)")
        elif isinstance(func, ast.Attribute):
            if (
                func.attr in _DANGEROUS_ATTRS
                and isinstance(func.value, ast.Name)
                and func.value.id in _DANGEROUS_MODULES
            ):
                issues.append(f"使用了危险调用 {func.value.id}.{func.attr}")
    return issues


def _open_mode_contains_write(node: ast.Call) -> bool:
    """判断 open(...) 是否使用了写模式（'w'/'a'/'x'）"""
    mode: str | None = None
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
        mode = node.args[1].value
    else:
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                mode = kw.value.value
                break
    return bool(mode and any(c in mode for c in "wax"))


def _first_error_detail(exc: Exception) -> str:
    """从 pydantic ValidationError 中提取首条错误的可读描述"""
    if isinstance(exc, ValidationError):
        try:
            first = exc.errors()[0]
            loc = ".".join(str(x) for x in first.get("loc", []))
            return f"{loc}: {first.get('msg', '')}" if loc else str(first.get("msg", exc))
        except Exception:
            return str(exc)
    return str(exc)
