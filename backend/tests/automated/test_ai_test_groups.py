"""AI 测试组生成——schema、校验流水线、Prompt、端点与 Docker 预检

覆盖方案第 4 节后端测试计划：
- TestGroup 字段、ID、分值边界、空 tests、重复 ID（共享校验）
- F/R 总分归一及浮点误差处理
- JSON 围栏、额外文本、非法维度、缺组、非法依赖和 pytest 语法错误
- Prompt 快照包含/不包含 hidden_tests，且私有测试不写入响应或错误
- 权限、题目不存在、ai_ready=false、超时、模型异常、首次失败后修复成功/失败
- 端点不落库
- Docker 预检：参考答案通过、collection 失败、未安装依赖被拒绝
"""
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.services.ai_client import AIServiceError, DeepSeekClient


def make_settings(**overrides):
    """构建测试 Settings（ai_ready=True）"""
    base = dict(
        _env_file=None,
        ai_base_url="https://aihub.codingpython.cn",
        ai_model="deepseek-v4-flash",
        ai_api_key="test-only-key",
        ai_max_retries=0,
        judge_timeout_seconds=5,
        judge_memory_limit_mb=256,
        judge_image="dai-judge-python:latest",
        judge_use_docker=True,
    )
    base.update(overrides)
    return Settings(**base)


def make_client(responses):
    """构建按调用顺序返回预设响应的 DeepSeek 客户端（MockTransport）"""
    queue = list(responses)

    def handler(request):
        payload = queue.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]
        })

    return DeepSeekClient(make_settings(), transport=httpx.MockTransport(handler))


def make_error_client(code: str, message: str, retryable: bool = False):
    """构建直接抛 AIServiceError 的客户端"""
    def handler(request):
        raise AIServiceError(code, message, retryable=retryable)

    return DeepSeekClient(make_settings(), transport=httpx.MockTransport(handler))


def valid_groups_payload(**overrides):
    """合法的生成结果 payload"""
    payload = {
        "test_groups": [
            {"id": "f1", "name": "基础功能", "dimension": "F", "max_score": 30,
             "tests": "def test_add():\n    assert add(1, 2) == 3"},
            {"id": "f2", "name": "核心功能", "dimension": "F", "max_score": 30,
             "tests": "def test_mul():\n    assert mul(2, 3) == 6"},
            {"id": "r1", "name": "边界", "dimension": "R", "max_score": 10,
             "tests": "def test_empty():\n    assert add([], []) == []"},
        ],
    }
    payload.update(overrides)
    return payload


# ═══════════════════════════════════════════════════════════════
# Prompt：快照与消息
# ═══════════════════════════════════════════════════════════════


def test_build_test_group_snapshot_fields():
    """快照包含题干、hidden_tests、参考答案与教师约束"""
    from app.services.ai_prompts import build_test_group_snapshot

    snapshot = build_test_group_snapshot(
        title="两数相加",
        description="实现加法",
        function_name="add",
        signature="def add(a, b)",
        starter_code="def add(a, b):\n    pass",
        hidden_tests="def test_hidden(): assert add(1, 1) == 2",
        reference_solution="def add(a, b): return a + b",
        teacher_constraints={"requirements_text": "不得使用全局变量"},
    )
    assert snapshot["title"] == "两数相加"
    assert snapshot["function_name"] == "add"
    assert snapshot["signature"] == "def add(a, b)"
    assert "def test_hidden()" in snapshot["hidden_tests"]
    assert snapshot["reference_solution"].startswith("def add")
    assert snapshot["teacher_constraints"]["requirements_text"] == "不得使用全局变量"


def test_build_test_group_messages_with_hidden_tests():
    """有 hidden_tests 时 user 消息包含私有测试（仅服务端 prompt 使用）"""
    from app.services.ai_prompts import build_test_group_messages, build_test_group_snapshot

    snapshot = build_test_group_snapshot(
        title="题目",
        hidden_tests="def test_secret(): assert True",
        reference_solution="def f(): pass",
    )
    messages = build_test_group_messages(snapshot)
    user_content = messages[1]["content"]
    assert messages[0]["role"] == "system"
    assert "<hidden_tests>" in user_content
    assert "def test_secret()" in user_content
    # 系统消息要求不回显私有测试
    assert "不得回显" in user_content


def test_build_test_group_messages_without_hidden_tests():
    """无 hidden_tests 时明确告知模型按题干、签名和参考答案推导"""
    from app.services.ai_prompts import build_test_group_messages, build_test_group_snapshot

    snapshot = build_test_group_snapshot(title="题目", hidden_tests=None)
    user_content = build_test_group_messages(snapshot)[1]["content"]
    assert "<hidden_tests>" not in user_content
    assert "无 hidden_tests" in user_content


def test_build_test_group_messages_with_fix_issues():
    """修复重试时携带脱敏问题列表"""
    from app.services.ai_prompts import build_test_group_messages, build_test_group_snapshot

    snapshot = build_test_group_snapshot(title="题目")
    messages = build_test_group_messages(snapshot, fix_issues=["缺少 R 组", "F1.tests 语法错误"])
    user_content = messages[1]["content"]
    assert "上一轮输出存在以下问题" in user_content
    assert "缺少 R 组" in user_content
    assert "F1.tests 语法错误" in user_content


# ═══════════════════════════════════════════════════════════════
# 校验流水线：归一化、分值、结构、语法、依赖
# ═══════════════════════════════════════════════════════════════


def test_valid_payload_normalized():
    """合法 payload 归一化：ID 大写、F=60、R=10"""
    from app.services.test_group_generator import validate_generated_payload

    groups, issues = validate_generated_payload(valid_groups_payload())
    assert issues == []
    ids = [g.id for g in groups]
    assert "F1" in ids and "F2" in ids and "R1" in ids
    assert sum(g.max_score for g in groups if g.dimension == "F") == 60
    assert sum(g.max_score for g in groups if g.dimension == "R") == 10


def test_payload_with_markdown_fence_stripped():
    """tests 携带 Markdown 围栏时自动去除"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"][0]["tests"] = '```python\ndef test_add():\n    assert True\n```'
    groups, issues = validate_generated_payload(payload)
    assert issues == []
    assert "```" not in groups[0].tests


def test_payload_with_extra_top_level_field_rejected():
    """顶层未知字段被拒绝（严格 JSON 契约）"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload(explanation="多余解释")
    _, issues = validate_generated_payload(payload)
    assert any("未知字段" in issue for issue in issues)


def test_payload_not_object_rejected():
    """非 JSON 对象被拒绝"""
    from app.services.test_group_generator import validate_generated_payload

    _, issues = validate_generated_payload(["not", "a", "dict"])
    assert any("不是 JSON 对象" in issue for issue in issues)


def test_payload_missing_groups_rejected():
    """缺少 test_groups 数组被拒绝"""
    from app.services.test_group_generator import validate_generated_payload

    _, issues = validate_generated_payload({})
    assert any("test_groups" in issue for issue in issues)


def test_invalid_dimension_rejected():
    """非法维度（如 A）产生 issues"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"][0]["dimension"] = "A"
    _, issues = validate_generated_payload(payload)
    assert issues, "非法维度必须产生 issues"


def test_missing_r_group_rejected():
    """缺 R 组产生 issues"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"] = [g for g in payload["test_groups"] if g["dimension"] != "R"]
    _, issues = validate_generated_payload(payload)
    assert any("缺少 R 组" in issue for issue in issues)


def test_too_many_f_groups_rejected():
    """F 组超过 2 个产生 issues"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"].append(
        {"id": "f3", "name": "额外", "dimension": "F", "max_score": 30,
         "tests": "def test_extra(): assert True"}
    )
    _, issues = validate_generated_payload(payload)
    assert any("F 组数量应为 1–2" in issue for issue in issues)


def test_duplicate_ids_suffixed():
    """冲突 ID 加后缀自动修复，保持唯一"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"][1]["id"] = "f1"
    groups, issues = validate_generated_payload(payload)
    assert issues == []
    ids = [g.id for g in groups]
    assert len(set(ids)) == len(ids)
    assert ids.count("F1") == 1


def test_syntax_error_reported_with_line():
    """pytest 语法错误产生带行号的 issues"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"][2]["tests"] = "def broken(:\n    pass"
    _, issues = validate_generated_payload(payload)
    assert any("语法错误" in issue and "第 1 行" in issue for issue in issues)


def test_disallowed_dependency_rejected():
    """未安装/不允许的依赖被拒绝"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"][0]["tests"] = (
        "import requests\n"
        "def test_net():\n    requests.get('http://example.com')\n"
    )
    _, issues = validate_generated_payload(payload)
    assert any("依赖 requests 未安装或不在允许范围" in issue for issue in issues)


def test_allowed_dependencies_accepted():
    """标准库与容器已有的 pytest/numpy/pandas/sklearn 允许"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"][0]["tests"] = (
        "import math\nimport numpy\nimport pandas\nimport sklearn\n"
        "import pytest\n"
        "def test_math():\n    assert math.pi > 3\n"
    )
    groups, issues = validate_generated_payload(payload)
    assert issues == []
    assert len(groups) == 3


def test_dangerous_apis_rejected():
    """危险 API（子进程/网络/文件写入/eval/exec）被拒绝"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"][1]["tests"] = (
        "import subprocess\n"
        "def test_hack():\n    subprocess.run(['rm', '-rf', '/'])\n"
    )
    _, issues = validate_generated_payload(payload)
    assert any("危险调用 subprocess.run" in issue for issue in issues)

    payload = valid_groups_payload()
    payload["test_groups"][1]["tests"] = "def test_evil():\n    eval('1+1')\n"
    _, issues = validate_generated_payload(payload)
    assert any("危险调用 eval" in issue for issue in issues)

    payload = valid_groups_payload()
    payload["test_groups"][1]["tests"] = (
        "def test_write():\n"
        "    with open('/tmp/x', 'w') as f:\n        f.write('x')\n"
    )
    _, issues = validate_generated_payload(payload)
    assert any("文件写入" in issue for issue in issues)


def test_score_rescaling_preserves_relative_weights():
    """分值归一保留相对权重：F 组 1:2 归为 20/40，R 组按 1:1 归为 5/5"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"] = [
        {"id": "F1", "name": "a", "dimension": "F", "max_score": 1,
         "tests": "def test_a(): assert True"},
        {"id": "F2", "name": "b", "dimension": "F", "max_score": 2,
         "tests": "def test_b(): assert True"},
        {"id": "R1", "name": "r1", "dimension": "R", "max_score": 1,
         "tests": "def test_r1(): assert True"},
        {"id": "R2", "name": "r2", "dimension": "R", "max_score": 1,
         "tests": "def test_r2(): assert True"},
    ]
    groups, issues = validate_generated_payload(payload)
    assert issues == []
    by_id = {g.id: g.max_score for g in groups}
    assert by_id["F1"] == 20
    assert by_id["F2"] == 40
    assert by_id["R1"] == 5
    assert by_id["R2"] == 5


def test_score_rescaling_last_group_absorbs_rounding():
    """小数误差由最后一组吸收，总分精确为 60/10"""
    from app.services.test_group_generator import validate_generated_payload

    payload = valid_groups_payload()
    payload["test_groups"] = [
        {"id": "F1", "name": "a", "dimension": "F", "max_score": 3,
         "tests": "def test_a(): assert True"},
        {"id": "F2", "name": "b", "dimension": "F", "max_score": 3,
         "tests": "def test_b(): assert True"},
        {"id": "R1", "name": "r", "dimension": "R", "max_score": 10,
         "tests": "def test_r(): assert True"},
    ]
    groups, issues = validate_generated_payload(payload)
    assert issues == []
    f_total = sum(g.max_score for g in groups if g.dimension == "F")
    assert abs(f_total - 60) < 1e-6
    by_id = {g.id: g.max_score for g in groups}
    assert abs(by_id["F1"] - 30) < 1e-6
    assert abs(by_id["F2"] - 30) < 1e-6


def test_generated_payload_passes_shared_config_validation():
    """合法生成结果必定通过现有 AIQuestionConfigUpdate 强校验（规则不漂移）"""
    from app.schemas.ai_grading import AIQuestionConfigUpdate
    from app.services.test_group_generator import validate_generated_payload

    groups, issues = validate_generated_payload(valid_groups_payload())
    assert issues == []
    AIQuestionConfigUpdate(
        grading_mode="active",
        test_groups=[g.model_dump() for g in groups],
    )


# ═══════════════════════════════════════════════════════════════
# Docker 预检
# ═══════════════════════════════════════════════════════════════


def _groups_for_preflight():
    from app.schemas.ai_grading import TestGroup

    return [
        TestGroup(id="F1", name="功能", dimension="F", max_score=60,
                  tests="def test_f(): assert True"),
        TestGroup(id="R1", name="鲁棒", dimension="R", max_score=10,
                  tests="def test_r(): assert True"),
    ]


def test_preflight_reference_solution_passes(tmp_path, monkeypatch):
    """有参考答案且全部通过 → 无 issues"""
    from app.services.test_group_generator import preflight_groups

    monkeypatch.setattr(
        "app.worker.judge_worker.run_test_groups",
        lambda *a, **k: {
            "results": {
                "F1": {"passed": 2, "failed": 0, "errors": 0, "skipped": 0},
                "R1": {"passed": 1, "failed": 0, "errors": 0, "skipped": 0},
            },
            "system_errors": [],
        },
    )
    issues = preflight_groups(
        _groups_for_preflight(), "def f(): pass", tmp_path, tmp_path,
        make_settings(), 5, 256,
    )
    assert issues == []


def test_preflight_reference_solution_failed(tmp_path, monkeypatch):
    """参考答案未通过某组 → issues"""
    from app.services.test_group_generator import preflight_groups

    monkeypatch.setattr(
        "app.worker.judge_worker.run_test_groups",
        lambda *a, **k: {
            "results": {
                "F1": {"passed": 1, "failed": 1, "errors": 0, "skipped": 0},
                "R1": {"passed": 1, "failed": 0, "errors": 0, "skipped": 0},
            },
            "system_errors": [],
        },
    )
    issues = preflight_groups(
        _groups_for_preflight(), "def f(): pass", tmp_path, tmp_path,
        make_settings(), 5, 256,
    )
    assert any("F1 未通过参考答案预检" in issue for issue in issues)


def test_preflight_collection_passes(tmp_path, monkeypatch):
    """无参考答案：collection 检查通过 → 无 issues"""
    from app.services.test_group_generator import preflight_groups

    monkeypatch.setattr(
        "app.worker.judge_worker._run_docker_pytest",
        lambda *a, **k: ("collected 2 items", "", 0, 100),
    )
    issues = preflight_groups(
        _groups_for_preflight(), None, tmp_path, tmp_path,
        make_settings(), 5, 256,
    )
    assert issues == []


def test_preflight_collection_writes_user_code_placeholder(tmp_path, monkeypatch):
    """回归（Bug 1）：无参考答案 collection 预检必须预写占位 user_code.py。

    测试代码会自动补 `from user_code import *`，若工作目录缺 user_code.py，
    pytest collection 阶段 import 失败（no tests collected, 1 error）→ 误报
    「无法收集」。此处模拟 pytest 该行为：缺 user_code.py 时返回 collection
    错误，预检应通过而非 502。
    """
    from pathlib import Path

    from app.services.test_group_generator import preflight_groups

    def fake_docker(workdir, settings, timeout_seconds, memory_limit_mb,
                    test_filename="test_group.py", host_workdir=None,
                    extra_args=None, image_ref=None):
        # 模拟真实 pytest：user_code.py 缺失 → collection error；存在 → 可收集
        if not (Path(workdir) / "user_code.py").exists():
            return "", "no tests collected, 1 error in 0.16s", 2, 100
        return "collected 2 items", "", 0, 100

    monkeypatch.setattr("app.worker.judge_worker._run_docker_pytest", fake_docker)
    issues = preflight_groups(
        _groups_for_preflight(), None, tmp_path, tmp_path,
        make_settings(), 5, 256,
    )
    assert issues == []


def test_preflight_collection_writes_to_docker_host_workdir(tmp_path, monkeypatch):
    """host_workdir 与写入目录不同（生产 DoD）时，预检文件必须写到 Docker 可见目录。"""
    from pathlib import Path as P

    from app.services.test_group_generator import preflight_groups

    workdir = tmp_path / "private-workdir"
    host = tmp_path / "docker-visible"
    workdir.mkdir()
    host.mkdir()
    seen = {}

    def fake_docker(workdir_arg, settings, timeout_seconds, memory_limit_mb,
                    test_filename="test_group.py", host_workdir=None,
                    extra_args=None, image_ref=None):
        seen["workdir"] = workdir_arg
        seen["host_workdir"] = host_workdir
        assert (P(host_workdir) / "test_group.py").exists()
        assert (P(host_workdir) / "user_code.py").exists()
        return "collected 2 items", "", 0, 100

    monkeypatch.setattr("app.worker.judge_worker._run_docker_pytest", fake_docker)
    issues = preflight_groups(
        _groups_for_preflight(), None, workdir, host,
        make_settings(), 5, 256,
    )
    assert issues == []
    # 预检目录建在 Docker 可见目录下，而不是私有 workdir
    assert P(seen["host_workdir"]).is_relative_to(host)
    assert P(seen["host_workdir"]).is_relative_to(workdir) is False
    # 临时预检目录已清理
    assert list(host.iterdir()) == []


def test_preflight_collection_failed(tmp_path, monkeypatch):
    """无参考答案：collection 失败 → issues"""
    from app.services.test_group_generator import preflight_groups

    monkeypatch.setattr(
        "app.worker.judge_worker._run_docker_pytest",
        lambda *a, **k: ("", "ERROR: fixture not found", 2, 100),
    )
    issues = preflight_groups(
        _groups_for_preflight(), None, tmp_path, tmp_path,
        make_settings(), 5, 256,
    )
    assert any("无法被 pytest 收集" in issue for issue in issues)


def test_preflight_docker_unavailable_raises(tmp_path, monkeypatch):
    """Docker 基础设施不可用 → PreflightUnavailableError（不是生成不合规）"""
    from app.services.test_group_generator import (
        PreflightUnavailableError, preflight_groups,
    )

    monkeypatch.setattr(
        "app.worker.judge_worker.run_test_groups",
        lambda *a, **k: {
            "results": {},
            "system_errors": ["测试组 F1 Docker 执行异常: [Errno 2] No such file or directory"],
        },
    )
    with pytest.raises(PreflightUnavailableError):
        preflight_groups(
            _groups_for_preflight(), "def f(): pass", tmp_path, tmp_path,
            make_settings(), 5, 256,
        )


# ═══════════════════════════════════════════════════════════════
# 生成服务：修复重试、warnings、错误上抛
# ═══════════════════════════════════════════════════════════════

_SNAPSHOT = {
    "title": "两数相加",
    "description": "实现加法",
    "function_name": "add",
    "signature": "def add(a, b)",
    "starter_code": "",
    "hidden_tests": "def test_hidden(): assert add(1, 1) == 2",
    "reference_solution": "def add(a, b): return a + b",
    "teacher_constraints": {},
}


def test_generate_success(tmp_path, monkeypatch):
    """首次生成即合规 → 返回可回填的响应，且只调用一次模型"""
    from app.services.test_group_generator import generate_test_groups

    client = make_client([valid_groups_payload()])
    monkeypatch.setattr(
        "app.services.test_group_generator.preflight_groups", lambda *a, **k: []
    )
    result = generate_test_groups(
        client, dict(_SNAPSHOT), make_settings(), workdir=tmp_path,
    )
    assert isinstance(result.test_groups, list)
    assert len(result.test_groups) == 3
    assert result.validation.f_total == 60
    assert result.validation.r_total == 10
    assert result.validation.group_count == 3
    assert result.generation_id


def test_generate_without_hidden_tests_warns(tmp_path, monkeypatch):
    """无 hidden_tests → warnings 提示按题干推导"""
    from app.services.test_group_generator import generate_test_groups

    client = make_client([valid_groups_payload()])
    monkeypatch.setattr(
        "app.services.test_group_generator.preflight_groups", lambda *a, **k: []
    )
    snapshot = dict(_SNAPSHOT, hidden_tests="")
    result = generate_test_groups(
        client, snapshot, make_settings(), workdir=tmp_path,
    )
    assert any("无 hidden_tests" in w for w in result.warnings)


def test_generate_truncates_long_hidden_tests(tmp_path, monkeypatch):
    """超长 hidden_tests 截断并在 warnings 告知"""
    from app.services.test_group_generator import generate_test_groups

    client = make_client([valid_groups_payload()])
    monkeypatch.setattr(
        "app.services.test_group_generator.preflight_groups", lambda *a, **k: []
    )
    snapshot = dict(_SNAPSHOT, hidden_tests="x" * 20000)
    result = generate_test_groups(
        client, snapshot, make_settings(), workdir=tmp_path,
    )
    assert any("截断" in w for w in result.warnings)


def test_generate_fix_retry_succeeds(tmp_path, monkeypatch):
    """首次不合规（缺 R 组）→ 一次修复调用后成功；共两次模型调用"""
    from app.services.test_group_generator import generate_test_groups

    class RecordingClient:
        def __init__(self, responses):
            self.responses = list(responses)
            self.calls = []

        def chat_json(self, messages, *, operation=None):
            self.calls.append(messages)
            return self.responses.pop(0)

    bad = valid_groups_payload()
    bad["test_groups"] = [g for g in bad["test_groups"] if g["dimension"] != "R"]
    client = RecordingClient([bad, valid_groups_payload()])
    monkeypatch.setattr(
        "app.services.test_group_generator.preflight_groups", lambda *a, **k: []
    )
    result = generate_test_groups(
        client, dict(_SNAPSHOT), make_settings(), workdir=tmp_path,
    )
    assert result.validation.r_group_count >= 1
    # 修复调用必须携带上一轮问题；共两次模型调用
    assert len(client.calls) == 2
    assert any("缺少 R 组" in m["content"] for msgs in client.calls for m in msgs)


def test_generate_fix_retry_fails(tmp_path, monkeypatch):
    """两次均不合规 → TestGroupValidationError 携带脱敏 issues"""
    from app.services.test_group_generator import (
        TestGroupValidationError, generate_test_groups,
    )

    bad = valid_groups_payload()
    bad["test_groups"] = [g for g in bad["test_groups"] if g["dimension"] != "R"]
    client = make_client([bad, bad])
    monkeypatch.setattr(
        "app.services.test_group_generator.preflight_groups", lambda *a, **k: []
    )
    with pytest.raises(TestGroupValidationError) as exc_info:
        generate_test_groups(client, dict(_SNAPSHOT), make_settings(), workdir=tmp_path)
    assert any("缺少 R 组" in i for i in exc_info.value.issues)


def test_generate_bad_json_fix_retry(tmp_path, monkeypatch):
    """首次 JSON 解析失败 → 一次修复调用后成功"""
    from app.services.test_group_generator import generate_test_groups

    class BadJsonClient:
        def __init__(self):
            self.calls = 0

        def chat_json(self, messages, *, operation=None):
            self.calls += 1
            if self.calls == 1:
                raise AIServiceError("bad_json", "AI 返回非 JSON 内容", retryable=True)
            return valid_groups_payload()

    monkeypatch.setattr(
        "app.services.test_group_generator.preflight_groups", lambda *a, **k: []
    )
    result = generate_test_groups(
        BadJsonClient(), dict(_SNAPSHOT), make_settings(), workdir=tmp_path,
    )
    assert result.validation.group_count == 3


def test_generate_timeout_propagates(tmp_path):
    """模型调用超时异常直接上抛（由端点映射 504）"""
    from app.services.test_group_generator import generate_test_groups

    client = make_error_client("timeout", "AI 请求超时", retryable=True)
    with pytest.raises(AIServiceError) as exc_info:
        generate_test_groups(client, dict(_SNAPSHOT), make_settings(), workdir=tmp_path)
    assert exc_info.value.code == "timeout"


def test_generate_auth_error_propagates(tmp_path):
    """认证失败（不可重试）直接上抛"""
    from app.services.test_group_generator import generate_test_groups

    client = make_error_client("http_401", "AI 认证失败", retryable=False)
    with pytest.raises(AIServiceError) as exc_info:
        generate_test_groups(client, dict(_SNAPSHOT), make_settings(), workdir=tmp_path)
    assert exc_info.value.code == "http_401"


# ═══════════════════════════════════════════════════════════════
# 端点
# ═══════════════════════════════════════════════════════════════


class FakeAIClient:
    """端点测试用：按调用顺序返回预设结果的 AI 客户端"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat_json(self, messages, *, operation=None):
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("模型调用次数超过预设")
        payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return payload


def _create_question(client, db_session_factory, teacher_username="gen_teacher",
                     kind="assignment", **question_kwargs):
    """创建教师 + 课程 + 题目，返回 (headers, question_id)"""
    from conftest import auth_header, create_user, login, seed_basic_environment

    seed_basic_environment(db_session_factory)
    create_user(db_session_factory, teacher_username, "teacher")
    token, _ = login(client, teacher_username)
    headers = auth_header(token)
    course_id = client.post(
        "/api/v1/courses", headers=headers,
        json={"title": f"{teacher_username}-course"},
    ).json()["id"]

    now = datetime.now(timezone.utc)
    if kind == "exam":
        exam_id = client.post(
            "/api/v1/exams", headers=headers,
            json={"course_id": course_id, "title": "gen-exam", "duration_minutes": 60,
                  "start_at": (now - timedelta(hours=1)).isoformat(),
                  "end_at": (now + timedelta(hours=1)).isoformat()},
        ).json()["id"]
        q = client.post(
            f"/api/v1/exams/{exam_id}/questions", headers=headers,
            json={
                "question_type": "code", "prompt": "实现加法", "points": 10,
                "correct_answer": {},
                "hidden_tests": "def test_secret_private(): assert True",
                "grading_mode": "active",
                **question_kwargs,
            },
        ).json()
        return headers, q["id"]

    assignment_id = client.post(
        "/api/v1/assignments", headers=headers,
        json={"title": "gen-assignment", "course_id": course_id},
    ).json()["id"]
    q = client.post(
        f"/api/v1/assignments/{assignment_id}/questions", headers=headers,
        json={
            "title": "两数相加", "function_name": "add",
            "signature": "def add(a, b)", "public_cases": [],
            "hidden_tests": "def test_secret_private(): assert True",
            "grading_mode": "active",
            **question_kwargs,
        },
    ).json()
    return headers, q["id"]


def _patch_ai(client, monkeypatch, responses):
    """替换端点的 DeepSeekClient 为 FakeAIClient，并跳过 Docker 预检"""
    fake = FakeAIClient(responses)
    monkeypatch.setattr("app.api.ai_grading.DeepSeekClient", lambda settings, **kw: fake)
    monkeypatch.setattr(
        "app.services.test_group_generator.preflight_groups", lambda *a, **k: []
    )
    return fake


def test_endpoint_requires_teacher(client, db_session_factory):
    """学生无权调用生成端点 → 403"""
    from conftest import auth_header, create_user, login

    create_user(db_session_factory, "gen_student", "student")
    token, _ = login(client, "gen_student")
    response = client.post(
        "/api/v1/ai-grading/questions/assignment/1/test-groups/generate",
        headers=auth_header(token), json={},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_endpoint_question_not_found(client, db_session_factory):
    """题目不存在 → 404"""
    from conftest import auth_header, create_user, login

    create_user(db_session_factory, "gen_teacher_missing", "teacher")
    token, _ = login(client, "gen_teacher_missing")
    response = client.post(
        "/api/v1/ai-grading/questions/assignment/99999/test-groups/generate",
        headers=auth_header(token), json={},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_endpoint_ai_not_ready(client, db_session_factory, test_settings):
    """ai_ready=false → 503 AI_NOT_READY"""
    from conftest import auth_header, create_user, login

    # 显式清空 API Key（开发环境 .env 可能已配置，避免受环境变量影响）
    test_settings.ai_api_key = SecretStr("")
    create_user(db_session_factory, "gen_teacher_nokey", "teacher")
    token, _ = login(client, "gen_teacher_nokey")
    headers = auth_header(token)
    course_id = client.post(
        "/api/v1/courses", headers=headers,
        json={"title": "nokey-course"},
    ).json()["id"]
    assignment_id = client.post(
        "/api/v1/assignments", headers=headers,
        json={"title": "nokey-assignment", "course_id": course_id},
    ).json()["id"]
    q = client.post(
        f"/api/v1/assignments/{assignment_id}/questions", headers=headers,
        json={"title": "q", "function_name": "f", "signature": "def f():",
              "public_cases": [], "hidden_tests": "def t(): pass",
              "grading_mode": "legacy"},
    ).json()
    # 默认测试配置无 API Key → ai_ready=False
    assert test_settings.ai_ready is False
    response = client.post(
        f"/api/v1/ai-grading/questions/assignment/{q['id']}/test-groups/generate",
        headers=headers, json={},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "AI_NOT_READY"


def test_endpoint_success_no_db_write(client, db_session_factory, test_settings, monkeypatch):
    """成功生成：合法响应、绝不落库"""
    from app.models import JudgeQuestion, QuestionRubric
    from sqlalchemy import select

    test_settings.ai_api_key = SecretStr("test-key")
    headers, qid = _create_question(client, db_session_factory)
    _patch_ai(client, monkeypatch, [valid_groups_payload()])

    response = client.post(
        f"/api/v1/ai-grading/questions/assignment/{qid}/test-groups/generate",
        headers=headers, json={
            "teacher_constraints": {"requirements_text": "不得使用全局变量"},
            "reference_solution": "def add(a, b): return a + b",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["validation"]["f_total"] == 60
    assert data["validation"]["r_total"] == 10
    assert data["validation"]["group_count"] == 3
    assert data["generation_id"]
    # 响应绝不包含 hidden_tests
    assert "test_secret_private" not in response.text

    # 不落库：题目配置原样、无新增 Rubric
    with db_session_factory() as db:
        q = db.get(JudgeQuestion, qid)
        assert q.test_groups == []
        assert q.reference_solution is None
        assert db.scalars(select(QuestionRubric)).all() == []


def test_endpoint_request_draft_fields_used(client, db_session_factory, test_settings, monkeypatch):
    """请求中的未保存草稿字段传给模型（prompt 含教师约束与参考答案）"""
    test_settings.ai_api_key = SecretStr("test-key")
    headers, qid = _create_question(client, db_session_factory)
    fake = _patch_ai(client, monkeypatch, [valid_groups_payload()])

    response = client.post(
        f"/api/v1/ai-grading/questions/assignment/{qid}/test-groups/generate",
        headers=headers, json={
            "teacher_constraints": {"requirements_text": "必须使用二分查找"},
            "reference_solution": "def add(a, b): return a + b",
        },
    )
    assert response.status_code == 200, response.text
    user_content = fake.calls[0][1]["content"]
    assert "必须使用二分查找" in user_content
    assert "def add(a, b): return a + b" in user_content
    # hidden_tests 仅用于 prompt（服务端），请求方不能伪造
    assert "test_secret_private" in fake.calls[0][1]["content"]


def test_endpoint_exam_kind_success(client, db_session_factory, test_settings, monkeypatch):
    """exam 题目同样可生成"""
    test_settings.ai_api_key = SecretStr("test-key")
    headers, qid = _create_question(client, db_session_factory, kind="exam")
    _patch_ai(client, monkeypatch, [valid_groups_payload()])

    response = client.post(
        f"/api/v1/ai-grading/questions/exam/{qid}/test-groups/generate",
        headers=headers, json={},
    )
    assert response.status_code == 200, response.text
    assert response.json()["validation"]["group_count"] == 3


def test_endpoint_invalid_payload_502_with_issues(client, db_session_factory, test_settings, monkeypatch):
    """两次生成均不合规 → 502，issues 可读且不含私有测试"""
    test_settings.ai_api_key = SecretStr("test-key")
    headers, qid = _create_question(client, db_session_factory)
    bad = valid_groups_payload()
    bad["test_groups"] = [g for g in bad["test_groups"] if g["dimension"] != "R"]
    _patch_ai(client, monkeypatch, [bad, bad])

    response = client.post(
        f"/api/v1/ai-grading/questions/assignment/{qid}/test-groups/generate",
        headers=headers, json={},
    )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["code"] == "AI_GENERATION_INVALID"
    assert any("缺少 R 组" in issue for issue in detail["fields"]["issues"])
    assert "test_secret_private" not in response.text


def test_endpoint_timeout_504(client, db_session_factory, test_settings, monkeypatch):
    """模型调用超时 → 504 AI_GENERATION_TIMEOUT"""
    test_settings.ai_api_key = SecretStr("test-key")
    headers, qid = _create_question(client, db_session_factory)
    _patch_ai(client, monkeypatch, [
        AIServiceError("timeout", "AI 请求超时", retryable=True),
    ])

    response = client.post(
        f"/api/v1/ai-grading/questions/assignment/{qid}/test-groups/generate",
        headers=headers, json={},
    )
    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "AI_GENERATION_TIMEOUT"


def test_endpoint_model_exception_502(client, db_session_factory, test_settings, monkeypatch):
    """模型层异常 → 502（含 429 与不可重试错误映射检查）"""
    test_settings.ai_api_key = SecretStr("test-key")
    headers, qid = _create_question(client, db_session_factory)
    _patch_ai(client, monkeypatch, [
        AIServiceError("http_429", "AI 服务暂时不可用 (429)", retryable=True),
    ])
    response = client.post(
        f"/api/v1/ai-grading/questions/assignment/{qid}/test-groups/generate",
        headers=headers, json={},
    )
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "AI_RATE_LIMITED"

    _patch_ai(client, monkeypatch, [
        AIServiceError("http_401", "AI 认证失败", retryable=False),
    ])
    response = client.post(
        f"/api/v1/ai-grading/questions/assignment/{qid}/test-groups/generate",
        headers=headers, json={},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["fields"]["retryable"] is False


def test_endpoint_rate_limited(client, db_session_factory, test_settings, monkeypatch, redis_client):
    """每用户每题目 60 秒内超过 5 次 → 429"""
    test_settings.ai_api_key = SecretStr("test-key")
    headers, qid = _create_question(client, db_session_factory)
    fake = _patch_ai(client, monkeypatch, [valid_groups_payload()] * 10)

    url = f"/api/v1/ai-grading/questions/assignment/{qid}/test-groups/generate"
    # 前 5 次成功
    for _ in range(5):
        response = client.post(url, headers=headers, json={})
        assert response.status_code == 200, response.text
    # 第 6 次被限流
    response = client.post(url, headers=headers, json={})
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "AI_RATE_LIMITED"


def test_endpoint_rejects_unknown_request_fields(client, db_session_factory, test_settings):
    """请求草稿字段不合法（未知字段）→ 422"""
    from conftest import auth_header, create_user, login

    test_settings.ai_api_key = SecretStr("test-key")
    create_user(db_session_factory, "gen_teacher_422", "teacher")
    token, _ = login(client, "gen_teacher_422")
    response = client.post(
        "/api/v1/ai-grading/questions/assignment/1/test-groups/generate",
        headers=auth_header(token),
        json={"hidden_tests": "def fake(): pass"},
    )
    assert response.status_code == 422
