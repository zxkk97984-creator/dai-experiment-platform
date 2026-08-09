"""镜像自动构建（Phase 1：builder）

- canonical_build_spec：版本 + 包集合 → 规范构建规格（包按 normalized name 排序 → manifest 哈希稳定）
- render_dockerfile：服务端 canonical manifest 渲染，不存在自由 Dockerfile 输入
- redact_build_log / truncate_build_log：日志脱敏与 60 KiB 尾部上限
- execute_build：构建 → 离线 smoke → digest 捕获；所有 Docker 命令使用 argv 调用，禁止 shell=True
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.models import EnvironmentVersion, PackageCatalog

# 平台固定运行依赖（不显示为教师可选教学库）
IPYKERNEL_VERSION = "6.29.5"
PYTEST_VERSION = "8.3.4"
PLATFORM_PYTHON_VERSION = "3.12"

# pytorch_cpu 官方 CPU wheel index——服务端内置，URL 绝不来自请求
TORCH_CPU_INDEX_URL = "https://download.pytorch.org/whl/cpu"

_KERNEL_RUNNER_PATH = Path(__file__).resolve().parents[1] / "docker" / "kernel" / "kernel_runner.py"


# ═══════════════════════════════════════════════════════════════
# 构建规格
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PackageEntry:
    pip_name: str
    locked_version: str
    import_names: tuple[str, ...]
    source_key: str  # pypi | pytorch_cpu


@dataclass(frozen=True)
class BuildSpec:
    """规范构建规格——同输入恒产生同 manifest / 同 Dockerfile 哈希"""

    base_image: str
    python_version: str
    profile_slug: str
    version_number: int
    repository: str
    packages: tuple[PackageEntry, ...]  # 已按 pip_name 排序
    kernel_runner_source: str

    @property
    def image_tag(self) -> str:
        """正式标签：dai-env:<slug>-v<version>——仅全部验证完成后才添加"""
        return f"{self.repository}:{self.profile_slug}-v{self.version_number}"

    def manifest_dict(self) -> dict:
        return {
            "base_image": self.base_image,
            "python_version": self.python_version,
            "repository": self.repository,
            "packages": [
                {
                    "pip_name": p.pip_name,
                    "locked_version": p.locked_version,
                    "import_names": list(p.import_names),
                    "source_key": p.source_key,
                }
                for p in self.packages
            ],
            "kernel_runner_sha256": hashlib.sha256(
                self.kernel_runner_source.encode("utf-8")
            ).hexdigest(),
        }


@dataclass(frozen=True)
class BuildResult:
    image_digest: str
    resolved_packages: dict  # pip freeze --all 解析结果
    smoke_report: dict


class BuildFailure(Exception):
    """构建失败（非超时）"""

    def __init__(self, message: str, code: str = "BUILD_FAILED"):
        super().__init__(message)
        self.code = code


class BuildTimeout(BuildFailure):
    """构建超时"""

    def __init__(self, message: str):
        super().__init__(message, code="BUILD_TIMEOUT")


def _load_kernel_runner() -> str:
    """可信 kernel_runner.py 内容——构建时复制进镜像，不暴露给教师"""
    try:
        return _KERNEL_RUNNER_PATH.read_text(encoding="utf-8")
    except OSError:
        # 允许测试环境无该文件（部署时随镜像提供）；manifest 哈希相应变化
        return ""


def canonical_build_spec(
    base_image_ref: str,
    profile_slug: str,
    version_number: int,
    packages: list[PackageCatalog],
    settings: Settings,
) -> BuildSpec:
    """从版本 + 包集合生成规范构建规格。

    包按 pip_name 排序，保证 manifest 与 Dockerfile 哈希稳定。
    """
    entries = sorted(
        (
            PackageEntry(
                pip_name=p.pip_name,
                locked_version=p.locked_version,
                import_names=tuple(p.import_names or []),
                source_key=p.source_key,
            )
            for p in packages
            if p.status == "active"
        ),
        key=lambda e: e.pip_name,
    )
    return BuildSpec(
        base_image=base_image_ref,
        python_version=PLATFORM_PYTHON_VERSION,
        profile_slug=profile_slug,
        version_number=version_number,
        repository=settings.env_image_repository,
        packages=tuple(entries),
        kernel_runner_source=_load_kernel_runner(),
    )


def spec_manifest_sha256(spec: BuildSpec) -> str:
    """manifest 哈希（CHAR(64)）——同 spec 恒同哈希"""
    return hashlib.sha256(
        json.dumps(spec.manifest_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def spec_dockerfile_sha256(dockerfile: str) -> str:
    return hashlib.sha256(dockerfile.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════
# Dockerfile 渲染
# ═══════════════════════════════════════════════════════════════


def _pip_requirement(entry: PackageEntry) -> str:
    """渲染单包安装需求——包名/版本已严格校验，双引号再防御性转义"""
    name = entry.pip_name.replace('"', '\\"')
    version = entry.locked_version.replace('"', '\\"')
    return f'"{name}=={version}"'


def render_dockerfile(spec: BuildSpec) -> str:
    """服务端 canonical manifest 渲染——FROM 只能来自配置基础镜像。

    - 安装固定 ipykernel 与 pytest（平台基础设施）
    - pytorch_cpu 包使用内置官方 CPU wheel index；URL 不来自请求
    - 复制可信 kernel_runner.py；创建 UID 1000 非 root 用户与 /course /work /tmp
    """
    lines = [
        "# 自动生成——由服务端 canonical manifest 渲染，请勿手动编辑",
        f"FROM {spec.base_image}",
        "ENV PYTHONUNBUFFERED=1 \\",
        "    PIP_NO_CACHE_DIR=1 \\",
        "    PIP_DISABLE_PIP_VERSION_CHECK=1",
        "# 平台固定运行依赖：ipykernel（Notebook）+ pytest（判题）",
        f'RUN pip install --no-cache-dir "ipykernel=={IPYKERNEL_VERSION}" "pytest=={PYTEST_VERSION}"',
    ]
    pypi_pkgs = [p for p in spec.packages if p.source_key != "pytorch_cpu"]
    torch_pkgs = [p for p in spec.packages if p.source_key == "pytorch_cpu"]
    if pypi_pkgs:
        lines.append("# 档位教学包（精确版本锁定）")
        lines.append("RUN pip install --no-cache-dir \\")
        for i, entry in enumerate(pypi_pkgs):
            sep = " \\" if i < len(pypi_pkgs) - 1 else ""
            lines.append(f"    {_pip_requirement(entry)}{sep}")
    if torch_pkgs:
        lines.append(f"# PyTorch CPU 档位——官方 CPU wheel index（服务端内置，不接受请求 URL）")
        lines.append("RUN pip install --no-cache-dir \\")
        for i, entry in enumerate(torch_pkgs):
            sep = " \\" if i < len(torch_pkgs) - 1 else ""
            lines.append(f"    --index-url {TORCH_CPU_INDEX_URL} {_pip_requirement(entry)}{sep}")
    lines += [
        "# 可信 kernel_runner.py（平台基础设施，不暴露给教师）",
        "COPY kernel_runner.py /opt/dai/kernel_runner.py",
        "# 非 root UID 1000 用户与工作目录",
        "RUN useradd --uid 1000 --create-home student \\",
        "    && mkdir -p /course /work /tmp \\",
        "    && chown -R student:student /course /work /tmp",
        "USER student",
        "WORKDIR /work",
        "",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 日志脱敏与截断
# ═══════════════════════════════════════════════════════════════

_URL_CREDENTIALS_RE = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)(?P<userinfo>[^/@\s]+)@")
_TOKEN_ATTR_RE = re.compile(
    r"(?i)(authorization|x-auth-token|x-api-key|api[_-]?key|access[_-]?token|token)"
    r"\s*[:=]\s*(?:bearer\s+)?(\S+)"
)
_SECRET_RE = re.compile(r"(?i)(--secret\s+id=)(\S+)")
_WIN_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"']+")
_POSIX_PATH_RE = re.compile(r"(?:/home|/Users|/root|/var|/srv|/tmp|/workspace)/[^\s\"']+")


def redact_build_log(text: str) -> str:
    """构建日志脱敏——入库前执行。

    覆盖：URL 用户名/密码、Authorization/API key/access token、Docker build secret、
    宿主机绝对目录（Windows 与 POSIX）。
    """
    if not text:
        return text
    out = _URL_CREDENTIALS_RE.sub(r"\g<scheme>***:***@", text)
    out = _TOKEN_ATTR_RE.sub(lambda m: f"{m.group(1)}=***", out)
    out = _SECRET_RE.sub(r"\1***", out)
    out = _WIN_PATH_RE.sub("/***", out)
    out = _POSIX_PATH_RE.sub("/***", out)
    return out


def truncate_build_log(text: str, max_bytes: int) -> str:
    """构建日志截断——超限时保留尾部（最新日志优先），行边界对齐避免截断中间行。

    截断点落在某行中间时前移到该行开头（最多浪费一行长度）；单行超过上限时保留其尾部。
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    decoded = encoded[-max_bytes:].decode("utf-8", errors="ignore")
    first_newline = decoded.find("\n")
    if first_newline != -1:
        decoded = decoded[first_newline + 1:]
    return decoded


# ═══════════════════════════════════════════════════════════════
# Docker 原语（模块级——测试 patch 点）
# ═══════════════════════════════════════════════════════════════

_BUILD_LEASE_SECONDS = 60


def _docker_build(
    temp_tag: str,
    dockerfile_path: Path,
    context_dir: Path,
    timeout_seconds: int,
    on_line,
) -> None:
    """docker build（argv 调用，禁止 shell）——流式日志，超时抛 BuildTimeout"""
    argv = [
        "docker", "build",
        "-t", temp_tag,
        "-f", str(dockerfile_path),
        str(context_dir),
    ]
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )
    started = time.monotonic()
    assert proc.stdout is not None
    for line in proc.stdout:
        if time.monotonic() - started > timeout_seconds:
            proc.kill()
            proc.wait()
            raise BuildTimeout(f"构建超过 {timeout_seconds} 秒")
        on_line(line.rstrip("\n"))
    returncode = proc.wait()
    if returncode != 0:
        raise BuildFailure(f"docker build 失败（exit={returncode}）")


def _docker_run(argv: list[str], timeout_seconds: int, on_line) -> int:
    """docker run（离线验证）——argv 调用，禁止 shell"""
    proc = subprocess.Popen(
        ["docker", "run", "--rm", *argv],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )
    started = time.monotonic()
    assert proc.stdout is not None
    for line in proc.stdout:
        if time.monotonic() - started > timeout_seconds:
            proc.kill()
            proc.wait()
            raise BuildTimeout(f"验证容器超过 {timeout_seconds} 秒")
        on_line(line.rstrip("\n"))
    return proc.wait()


def _docker_inspect_id(tag: str) -> str:
    """捕获本地内容寻址 digest：docker image inspect <tag> --format "{{.Id}}" """
    result = subprocess.run(
        ["docker", "image", "inspect", tag, "--format", "{{.Id}}"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise BuildFailure(f"无法获取镜像 digest: {result.stderr.strip()[:200]}")
    digest = result.stdout.strip()
    if not digest.startswith("sha256:"):
        raise BuildFailure(f"镜像 digest 格式异常: {digest[:100]}")
    return digest


def _docker_tag(source: str, target: str) -> None:
    """添加正式标签——仅全部验证完成后调用"""
    result = subprocess.run(
        ["docker", "tag", source, target], capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise BuildFailure(f"添加正式标签失败: {result.stderr.strip()[:200]}")


# ═══════════════════════════════════════════════════════════════
# 构建执行
# ═══════════════════════════════════════════════════════════════

_SMOKE_SCRIPT = """import importlib, json
IMPORTS = json.loads(%r)
results = {}
failed = []
for name in IMPORTS:
    try:
        importlib.import_module(name)
        results[name] = True
    except Exception:
        results[name] = False
        failed.append(name)
print("DAI_SMOKE_IMPORTS=" + json.dumps(results))
if failed:
    print("DAI_SMOKE_FAILED=" + json.dumps(failed))
    raise SystemExit(1)
"""


def _parse_pip_freeze(lines: list[str]) -> dict:
    """解析 `pip freeze --all` 输出为 {包名: 版本}——resolved_packages 冻结依据"""
    out: dict = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " @ " in line:  # VCS/URL 安装形式（不应出现在受控环境，防御跳过）
            continue
        if "==" in line:
            name, _, version = line.partition("==")
            out[name.strip()] = version.strip()
    return out


def _run_smoke(
    temp_tag: str,
    import_names: list[str],
    timeout_seconds: int,
    on_line,
) -> tuple[dict, dict]:
    """离线容器验证：catalog import 名 + pytest/ipykernel import + pip freeze --all。

    容器参数保持判题/Kernel 一致：--network none、非 root。
    任一必装模块 import 失败 → exit 1 → BuildFailure(SMOKE_IMPORT_FAILED)。
    """
    smoke_imports = sorted(set(import_names) | {"pytest", "ipykernel"})
    script = _SMOKE_SCRIPT % json.dumps(smoke_imports)
    import_lines: list[str] = []
    import_report: dict = {}

    argv = [
        "--network", "none", "--user", "1000:1000",
        temp_tag, "python", "-c", script,
    ]
    code = _docker_run(argv, timeout_seconds, lambda line: (import_lines.append(line), on_line(line)))
    for line in import_lines:
        if line.startswith("DAI_SMOKE_IMPORTS="):
            try:
                import_report = json.loads(line.split("=", 1)[1])
            except json.JSONDecodeError:
                import_report = {}
    if code != 0:
        failed = [name for name, ok in import_report.items() if not ok]
        detail = f"（缺失: {', '.join(failed[:10])}）" if failed else ""
        raise BuildFailure(f"镜像 import smoke 失败（exit={code}）{detail}", code="SMOKE_IMPORT_FAILED")

    freeze_lines: list[str] = []
    freeze_code = _docker_run(
        ["--network", "none", "--user", "1000:1000", temp_tag, "python", "-m", "pip", "freeze", "--all"],
        timeout_seconds,
        lambda line: (freeze_lines.append(line), on_line(line)),
    )
    pip_freeze = _parse_pip_freeze(freeze_lines) if freeze_code == 0 else {}
    return import_report, pip_freeze


def execute_build(
    spec: BuildSpec,
    settings: Settings,
    *,
    on_log=None,
    temp_tag: str | None = None,
    dockerfile_text: str | None = None,
    kernel_runner_text: str | None = None,
) -> BuildResult:
    """执行一次完整构建：docker build → 离线 smoke → digest 捕获。

    - 临时 tag 构建（不覆盖已发布标签）；正式标签由 Worker 在全部验证后添加
    - 失败抛 BuildFailure/BuildTimeout，不修改任何 DB 状态
    """
    on_log = on_log or (lambda line: None)
    if temp_tag is None:
        temp_tag = f"{spec.repository}:build-{spec.profile_slug}-{spec.version_number}-{int(time.time())}"
    dockerfile = dockerfile_text or render_dockerfile(spec)
    runner_text = kernel_runner_text if kernel_runner_text is not None else spec.kernel_runner_source

    with tempfile.TemporaryDirectory(prefix="dai-env-build-") as tmp:
        context_dir = Path(tmp)
        (context_dir / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        (context_dir / "kernel_runner.py").write_text(runner_text, encoding="utf-8")
        on_log(f"# 构建临时标签: {temp_tag}")
        _docker_build(temp_tag, context_dir / "Dockerfile", context_dir,
                      settings.env_build_timeout_seconds, on_log)

        on_log("# 离线 import smoke 验证")
        import_names = [name for p in spec.packages for name in p.import_names]
        import_report, pip_freeze = _run_smoke(
            temp_tag, import_names, settings.env_build_timeout_seconds, on_log
        )
        on_log("# 捕获镜像 digest")
        digest = _docker_inspect_id(temp_tag)
        on_log(f"# digest={digest}")

        return BuildResult(
            image_digest=digest,
            resolved_packages=pip_freeze,
            smoke_report={"imports": import_report},
        )
