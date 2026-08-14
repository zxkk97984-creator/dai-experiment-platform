"""环境构建 Worker / Builder / 种子测试（Phase 1）

全部使用 mock/fixture，不执行真实 docker build：
- canonical_build_spec / render_dockerfile：纯函数
- redact_build_log / truncate_build_log：日志脱敏与 60 KiB 上限
- worker 状态机：queued→building→succeeded/failed/timed_out、lease 恢复、失败不动旧版本
- seed 幂等与入队
"""
from __future__ import annotations
import pytest
pytestmark = pytest.mark.no_auto_env_seed

import json
from datetime import timedelta
from unittest.mock import patch


from app.models import (
    EnvironmentBuildJob,
    EnvironmentProfile,
    EnvironmentVersion,
    PackageCatalog,
    ProfileVersionPackage,
)
from app.services.environment_builder import (
    BuildFailure,
    BuildTimeout,
    _SMOKE_SCRIPT,
    canonical_build_spec,
    redact_build_log,
    render_dockerfile,
    truncate_build_log,
)
from app.services.environment_seed import seed_environment_catalog
from app.services.time_utils import utc_now
from app.worker import environment_builder_worker as worker

FAKE_DIGEST = "sha256:" + "f" * 64


# ═══════════════════════════════════════════════════════════════
# 测试数据工厂
# ═══════════════════════════════════════════════════════════════

def _make_package(db, id_, name="numpy", version="2.1.3", source="pypi", imports=None, tags=None):
    pkg = PackageCatalog(
        id=id_,
        normalized_name=name,
        pip_name=name,
        locked_version=version,
        import_names=imports or [name],
        category_tags=tags or ["data"],
        source_key=source,
        status="active",
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


def _make_profile(db, id_=1, slug="basic", display_name="Python 基础"):
    prof = EnvironmentProfile(id=id_, slug=slug, display_name=display_name, status="active")
    db.add(prof)
    db.commit()
    db.refresh(prof)
    return prof


def _make_version(db, profile_id, id_=1, version_number=1, status="draft"):
    ver = EnvironmentVersion(
        id=id_,
        profile_id=profile_id,
        version_number=version_number,
        status=status,
        base_image_ref="python:3.12-slim@sha256:" + "0" * 64,
        minimum_memory_mb=256,
        manifest_sha256="m" * 64,
    )
    db.add(ver)
    db.commit()
    db.refresh(ver)
    return ver


def _link_packages(db, version_id, package_ids):
    for order, pid in enumerate(package_ids):
        db.add(ProfileVersionPackage(
            environment_version_id=version_id, package_catalog_id=pid, display_order=order
        ))
    db.commit()


def _make_job(db, version_id, id_=1, status="queued", attempt=1):
    job = EnvironmentBuildJob(
        id=id_, environment_version_id=version_id, status=status, attempt_number=attempt
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ═══════════════════════════════════════════════════════════════
# canonical_build_spec / render_dockerfile
# ═══════════════════════════════════════════════════════════════

def test_build_spec_sorts_packages_stably(db_session_factory, test_settings):
    with db_session_factory() as db:
        prof = _make_profile(db)
        ver = _make_version(db, prof.id)
        z = _make_package(db, 1, name="zstd", version="1.5.0")
        a = _make_package(db, 2, name="attrs", version="24.0.0")
        _link_packages(db, ver.id, [z.id, a.id])  # 乱序传入

        spec = canonical_build_spec(ver.base_image_ref, prof.slug, ver.version_number, [z, a], test_settings)
        names = [p.pip_name for p in spec.packages]
        assert names == ["attrs", "zstd"]  # 按名称稳定排序


def test_build_spec_includes_non_empty_kernel_runner_source(db_session_factory, test_settings):
    """每个环境镜像都必须携带可执行的可信 runner 源码。"""
    with db_session_factory() as db:
        prof = _make_profile(db)
        ver = _make_version(db, prof.id)
        spec = canonical_build_spec(ver.base_image_ref, prof.slug, ver.version_number, [], test_settings)

    assert spec.kernel_runner_source.strip()
    assert "BlockingKernelClient" in spec.kernel_runner_source


def test_manifest_hash_stable(db_session_factory, test_settings):
    with db_session_factory() as db:
        prof = _make_profile(db)
        ver = _make_version(db, prof.id)
        a = _make_package(db, 1, name="attrs", version="24.0.0")
        b = _make_package(db, 2, name="zstd", version="1.5.0")
        spec1 = canonical_build_spec(ver.base_image_ref, prof.slug, ver.version_number, [a, b], test_settings)
        spec2 = canonical_build_spec(ver.base_image_ref, prof.slug, ver.version_number, [a, b], test_settings)
        m1 = json.dumps(spec1.manifest_dict(), sort_keys=True, separators=(",", ":"))
        m2 = json.dumps(spec2.manifest_dict(), sort_keys=True, separators=(",", ":"))
        assert m1 == m2


def test_dockerfile_rendering_rules(db_session_factory, test_settings):
    with db_session_factory() as db:
        prof = _make_profile(db, slug="basic")
        ver = _make_version(db, prof.id)
        pkg = _make_package(db, 1, name="numpy", version="2.1.3")
        _link_packages(db, ver.id, [pkg.id])
        spec = canonical_build_spec(ver.base_image_ref, prof.slug, ver.version_number, [pkg], test_settings)
        dockerfile = render_dockerfile(spec)

    # FROM 只能来自配置基础镜像（不可由请求注入）
    assert "FROM python:3.12-slim" in dockerfile
    # 平台固定依赖
    assert "ipykernel==6.29.5" in dockerfile
    assert "pytest" in dockerfile
    # 精确版本包
    assert '"numpy==2.1.3"' in dockerfile
    # 非 root UID 1000 + 工作目录
    assert "useradd" in dockerfile and "1000" in dockerfile
    assert "student" in dockerfile
    assert "/course" in dockerfile and "/work" in dockerfile and "/tmp" in dockerfile
    # 可信 kernel_runner.py 复制
    assert "kernel_runner.py" in dockerfile
    assert "COPY kernel_runner.py /opt/dai/kernel_runner.py" in dockerfile
    assert "test -s /opt/dai/kernel_runner.py" in dockerfile
    # 无任意安装命令输入面：不得出现裸 pip install 之外的 argv 注入
    assert "--index-url https://download.pytorch.org/whl/cpu" not in dockerfile  # basic 无 torch


def test_dockerfile_pytorch_cpu_uses_builtin_index(db_session_factory, test_settings):
    with db_session_factory() as db:
        prof = _make_profile(db, slug="torch-cpu")
        ver = _make_version(db, prof.id)
        torch = _make_package(db, 1, name="torch", version="2.6.0+cpu",
                              source="pytorch_cpu", imports=["torch"], tags=["machine-learning"])
        _link_packages(db, ver.id, [torch.id])
        spec = canonical_build_spec(ver.base_image_ref, prof.slug, ver.version_number, [torch], test_settings)
        dockerfile = render_dockerfile(spec)
    assert '--index-url https://download.pytorch.org/whl/cpu "torch==2.6.0+cpu"' in dockerfile


# ═══════════════════════════════════════════════════════════════
# 日志脱敏与截断
# ═══════════════════════════════════════════════════════════════

def test_smoke_script_renders_executable_python():
    """回归（Phase 6 真实构建暴露）：_SMOKE_SCRIPT 用 % 格式化，`{{}}` 不会被转义，
    容器内 `results = {{}}` 被解析为含 dict 的 set → TypeError: unhashable type: 'dict'。
    渲染结果必须可通过 compile() 并在 exec 后产生合法 JSON 报告。
    """
    rendered = _SMOKE_SCRIPT % json.dumps(["pytest", "ipykernel"])
    # % 格式化不会处理 {{}}——出现花括号转义残留即失败
    assert "{{" not in rendered and "}}" not in rendered
    compile(rendered, "<smoke-script>", "exec")

    namespace: dict = {}
    exec(rendered, namespace)
    # 执行后 results 是合法 dict（容器内以此生成 DAI_SMOKE_IMPORTS JSON 报告）
    results = namespace["results"]
    assert isinstance(results, dict)
    assert results.get("pytest") is True  # 测试环境必有 pytest
    # 允许 import 失败的包进入 failed 列表而不抛 TypeError（不可哈希即崩溃）
    assert isinstance(namespace["failed"], list)


def test_redact_log_credentials():
    log = (
        "#1 [internal] pull git@github.com:user/repo.git\n"
        "Step 3/8 : RUN pip install https://user:secretpass@evil.example/pypi\n"
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def\n"
        "access_token=1234567890abcdef\n"
        "api_key=sk-live-abcdef123456\n"
        "docker run --secret id=mysecret,src=/home/admin/.ssh/id_rsa\n"
    )
    out = redact_build_log(log)
    assert "secretpass" not in out
    assert "user:" not in out  # URL 用户名密码已脱敏
    assert "eyJhbGciOiJIUzI1NiJ9" not in out
    assert "1234567890abcdef" not in out
    assert "sk-live-abcdef123456" not in out
    assert "/home/admin/.ssh/id_rsa" not in out
    assert "***" in out


def test_redact_log_host_paths():
    log = "failed to solve: /home/user/project/storage/studio/x.ipynb\n"
    assert "/home/user/project" not in redact_build_log(log)
    log2 = r"COPY C:\Users\admin\Documents\secret\key.pem"
    assert "C:\\Users\\admin" not in redact_build_log(log2)


def test_truncate_log_keeps_tail_60kib():
    long_log = "LINE_" + ("x" * 80) + "\n"
    big = long_log * 2000  # 远超 60 KiB
    assert len(big.encode()) > 60 * 1024
    out = truncate_build_log(big, max_bytes=60 * 1024)
    assert len(out.encode()) <= 60 * 1024
    # 保留尾部（最新日志优先，最后一行完整）
    assert out.rstrip("\n").endswith(long_log.rstrip("\n"))


def test_truncate_log_short_log_unchanged():
    assert truncate_build_log("short", 60 * 1024) == "short"


# ═══════════════════════════════════════════════════════════════
# Worker 状态机
# ═══════════════════════════════════════════════════════════════

def _setup_env(db):
    prof = _make_profile(db)
    ver = _make_version(db, prof.id)
    pkg = _make_package(db, 1)
    _link_packages(db, ver.id, [pkg.id])
    return prof, ver, pkg


def test_claim_build_job_conditional_update(db_session_factory):
    with db_session_factory() as db:
        _, ver, _ = _setup_env(db)
        job = _make_job(db, ver.id)
        now = utc_now()
        assert worker.claim_build_job(db, job.id, "worker-1", now) is True
        assert job.status == "building"
        assert job.worker_id == "worker-1"
        # 并发抢占：已被 claim 的任务返回 False
        assert worker.claim_build_job(db, job.id, "worker-2", now) is False
        assert job.status == "building"


def test_build_success_writes_digest_and_available(db_session_factory, test_settings):
    with db_session_factory() as db:
        _, ver, _ = _setup_env(db)
        job = _make_job(db, ver.id)
        now = utc_now()
        assert worker.claim_build_job(db, job.id, "worker-1", now)

        with patch.object(worker, "execute_build", return_value=worker.BuildResult(
            image_digest=FAKE_DIGEST,
            resolved_packages={"numpy": "2.1.3", "pip": "24.0"},
            smoke_report={"imports": ["numpy"], "passed": True},
        )) as mock_build, patch.object(worker, "_tag_official_image") as mock_tag:
            final = worker.process_build(db, test_settings, "worker-1", job.id, now)

        assert final == "succeeded"
        db.refresh(job)
        db.refresh(ver)
        assert job.status == "succeeded"
        assert job.finished_at is not None
        assert ver.status == "available"
        assert ver.image_digest == FAKE_DIGEST
        assert ver.image_tag == f"{test_settings.env_image_repository}:basic-v1"
        assert ver.available_at is not None
        assert ver.resolved_packages["numpy"] == "2.1.3"
        mock_build.assert_called_once()
        mock_tag.assert_called_once()


def test_build_failure_keeps_version_draft(db_session_factory, test_settings):
    with db_session_factory() as db:
        _, ver, _ = _setup_env(db)
        job = _make_job(db, ver.id)
        now = utc_now()
        assert worker.claim_build_job(db, job.id, "worker-1", now)

        with patch.object(worker, "execute_build", side_effect=BuildFailure("pip install 失败", code="BUILD_FAILED")):
            final = worker.process_build(db, test_settings, "worker-1", job.id, now)

        assert final == "failed"
        db.refresh(job)
        db.refresh(ver)
        assert job.status == "failed"
        assert job.error_code == "BUILD_FAILED"
        assert "pip install 失败" in job.error_message
        assert ver.status == "draft"  # 失败不修改旧版本
        assert ver.image_digest is None


def test_build_timeout_marks_timed_out(db_session_factory, test_settings):
    with db_session_factory() as db:
        _, ver, _ = _setup_env(db)
        job = _make_job(db, ver.id)
        now = utc_now()
        assert worker.claim_build_job(db, job.id, "worker-1", now)

        with patch.object(worker, "execute_build", side_effect=BuildTimeout("构建超过 3600 秒")):
            final = worker.process_build(db, test_settings, "worker-1", job.id, now)

        assert final == "timed_out"
        db.refresh(job)
        assert job.status == "timed_out"
        assert job.error_code == "BUILD_TIMEOUT"


def test_worker_crash_lease_expired_requeued(db_session_factory, test_settings, redis_client):
    """Worker 崩溃后 lease 过期：building → queued，其他 Worker 可接管。

    回归（Phase 6 真实构建暴露）：Redis 唤醒消息已被崩溃 Worker 消费，
    恢复时必须重新推送，否则任务永久卡在 queued。
    """
    with db_session_factory() as db:
        _, ver, _ = _setup_env(db)
        now = utc_now()
        job = _make_job(db, ver.id, status="building")
        job.worker_id = "dead-worker"
        job.started_at = now - timedelta(minutes=2)
        job.lease_until = now - timedelta(minutes=1)  # lease 已过期
        db.commit()

        stats = worker.recover_stale_builds(db, test_settings, now, redis_client=redis_client)
        db.refresh(job)
        assert job.status == "queued"
        assert job.worker_id is None
        assert stats["requeued"] == 1
        # 必须重新推送唤醒消息（原消息已被崩溃 Worker 消费）
        msg = redis_client.lindex(test_settings.env_build_queue_name, 0)
        assert msg is not None
        assert json.loads(msg)["version_id"] == ver.id


def test_worker_crash_beyond_timeout_timed_out(db_session_factory, test_settings):
    """构建超时（started_at 超过阈值）且 lease 过期 → timed_out"""
    with db_session_factory() as db:
        _, ver, _ = _setup_env(db)
        now = utc_now()
        job = _make_job(db, ver.id, status="building")
        job.started_at = now - timedelta(seconds=test_settings.env_build_timeout_seconds + 60)
        job.lease_until = now - timedelta(seconds=1)
        db.commit()

        stats = worker.recover_stale_builds(db, test_settings, now)
        db.refresh(job)
        assert job.status == "timed_out"
        assert job.error_code == "BUILD_TIMEOUT"
        assert stats["timed_out"] == 1


def test_build_log_redacted_and_truncated_in_job(db_session_factory, test_settings):
    """execute_build 回调的日志在入库前脱敏并限制 60 KiB"""
    with db_session_factory() as db:
        _, ver, _ = _setup_env(db)
        job = _make_job(db, ver.id)
        now = utc_now()
        assert worker.claim_build_job(db, job.id, "worker-1", now)

        secret_line = "pull https://user:supersecret@example.com/pkg\n"

        def fake_build(*, on_log=None, **_kw):
            for _ in range(100):
                on_log(secret_line)
            return worker.BuildResult(image_digest=FAKE_DIGEST, resolved_packages={}, smoke_report={})

        with patch.object(worker, "execute_build", side_effect=fake_build):
            worker.process_build(db, test_settings, "worker-1", job.id, now)

        db.refresh(job)
        assert "supersecret" not in (job.log_text or "")
        assert len((job.log_text or "").encode()) <= test_settings.env_build_log_max_bytes


def test_retry_job_runs_after_failure(db_session_factory, test_settings):
    """失败后可创建 retry 任务（关联 retry_of_id），成功后旧 job 保持失败"""
    with db_session_factory() as db:
        _, ver, _ = _setup_env(db)
        job1 = _make_job(db, ver.id, id_=1, status="failed", attempt=1)
        job1.error_code = "BUILD_FAILED"
        db.commit()
        job2 = _make_job(db, ver.id, id_=2, status="queued", attempt=2)
        job2.retry_of_id = job1.id
        db.commit()
        now = utc_now()
        assert worker.claim_build_job(db, job2.id, "worker-1", now)
        with patch.object(worker, "execute_build", return_value=worker.BuildResult(
            image_digest=FAKE_DIGEST, resolved_packages={}, smoke_report={}
        )):
            final = worker.process_build(db, test_settings, "worker-1", job2.id, now)
        assert final == "succeeded"
        db.refresh(job1)
        db.refresh(job2)
        assert job1.status == "failed"  # 历史失败记录保留
        assert job2.status == "succeeded"
        assert job2.retry_of_id == job1.id


# ═══════════════════════════════════════════════════════════════
# seed 幂等
# ═══════════════════════════════════════════════════════════════

def test_seed_creates_profiles_packages_versions(db_session_factory, test_settings):
    with db_session_factory() as db:
        result = seed_environment_catalog(db, test_settings)
        assert len(result.profiles_created) == 3
        assert len(result.packages_created) == 7
        assert len(result.versions_created) == 3

        # basic=1 包（pytest）、data=6 包、torch-cpu=7 包（共 14 条关联）
        links = db.query(ProfileVersionPackage).all()
        assert len(links) == 1 + 6 + 7
        prof = db.query(EnvironmentProfile).filter(EnvironmentProfile.slug == "torch-cpu").one()
        assert prof.versions[0].minimum_memory_mb == 2048
        assert prof.versions[0].status == "draft"


def test_seed_idempotent(db_session_factory, test_settings):
    with db_session_factory() as db:
        seed_environment_catalog(db, test_settings)
        second = seed_environment_catalog(db, test_settings)
        assert second.profiles_created == []
        assert second.packages_created == []
        assert second.versions_created == []
        assert len(db.query(EnvironmentProfile).all()) == 3
        assert len(db.query(PackageCatalog).all()) == 7
        assert len(db.query(EnvironmentVersion).all()) == 3
        assert len(db.query(ProfileVersionPackage).all()) == 14


def test_seed_enqueue_is_idempotent(db_session_factory, test_settings, redis_client):
    with db_session_factory() as db:
        first = seed_environment_catalog(db, test_settings, enqueue=True, redis_client=redis_client)
        assert len(first.enqueued) == 3
        assert redis_client.llen(test_settings.env_build_queue_name) == 3
        versions = db.query(EnvironmentVersion).all()
        assert all(v.status == "queued" for v in versions)

        # 二次 enqueue：不重复入队
        second = seed_environment_catalog(db, test_settings, enqueue=True, redis_client=redis_client)
        assert second.enqueued == []
        assert redis_client.llen(test_settings.env_build_queue_name) == 3


def test_seed_skips_available_versions(db_session_factory, test_settings, redis_client):
    with db_session_factory() as db:
        seed_environment_catalog(db, test_settings)
        basic = db.query(EnvironmentVersion).join(EnvironmentProfile).filter(
            EnvironmentProfile.slug == "basic"
        ).one()
        basic.status = "available"
        db.commit()
        result = seed_environment_catalog(db, test_settings, enqueue=True, redis_client=redis_client)
        assert "basic" in result.already_available
        assert "basic" not in result.enqueued
        assert len(result.enqueued) == 2


def test_seed_never_uses_arbitrary_requirements(db_session_factory, test_settings):
    """seed 数据全部来自内置常量：无 requirements/Dockerfile/pip 参数输入"""
    with db_session_factory() as db:
        seed_environment_catalog(db, test_settings)
        pkgs = db.query(PackageCatalog).all()
        assert all(p.source_key in ("pypi", "pytorch_cpu") for p in pkgs)
        assert all(p.status == "active" for p in pkgs)
        assert all(p.normalized_name == p.pip_name for p in pkgs)  # 内置数据已归一化
