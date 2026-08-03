"""
Kernel Session 管理器

架构：
- docker run 启动持久 ipykernel（network none，无 -p），conn file 在 /tmp/conn.json
- 每次 execute 用 docker exec -i <container> python /.dai/kernel_runner.py
- trusted runner 在容器内通过 jupyter_client.BlockingKernelClient 连接 ipykernel
- 学生代码通过 stdin JSON 传入，不出现于 argv
- 硬超时 30s → rm -f 旧容器 + 立即 create_session 重建
- Redis 持久化 session + hidden init marker
"""
import json
import logging
import os
import secrets
import subprocess
import time
from typing import Optional

from app.config import Settings, get_settings

logger = logging.getLogger("kernel_manager")

KERNEL_HARD_TIMEOUT = 30
RUNNER_PATH = "/.dai/kernel_runner.py"


class KernelSession:
    """单个 kernel session 的运行时状态"""

    def __init__(self, record_id: int, container_name: str, conn_info: dict,
                 lesson_storage_dir: str = "",
                 initialized_template_version_id: int | None = None):
        self.record_id = record_id
        self.container_name = container_name
        self.conn_info = conn_info
        self.lesson_storage_dir = lesson_storage_dir
        self.initialized_template_version_id = initialized_template_version_id
        self.last_active_at = time.time()

    @property
    def is_alive(self) -> bool:
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name={self.container_name}"],
            capture_output=True, text=True,
        )
        return bool(result.stdout.strip())

    def to_redis_dict(self) -> dict:
        return {
            "container_name": self.container_name,
            "conn_info": self.conn_info,
            "lesson_storage_dir": self.lesson_storage_dir,
            "initialized_template_version_id": self.initialized_template_version_id,
        }

    @classmethod
    def from_redis_dict(cls, record_id: int, data: dict) -> "KernelSession":
        return cls(
            record_id=record_id,
            container_name=data["container_name"],
            conn_info=data["conn_info"],
            lesson_storage_dir=data.get("lesson_storage_dir", ""),
            initialized_template_version_id=data.get("initialized_template_version_id"),
        )


class KernelManager:
    """管理所有 kernel session 的生命周期"""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._sessions: dict[int, KernelSession] = {}

    def _make_container_name(self, record_id: int) -> str:
        return f"dai-kernel-rec-{record_id}"

    def _make_lock_token(self) -> str:
        return secrets.token_hex(16)

    def _kernel_path(self, *parts: str) -> str:
        """返回 API/Worker 容器内可写的 Kernel 共享目录路径。"""
        if self.settings.judge_work_dir:
            return os.path.join(self.settings.judge_work_dir, *parts)
        return os.path.join(os.environ.get("TEMP", "/tmp"), *parts)

    def _docker_host_path(self, container_path: str) -> str:
        """把共享目录中的容器路径转换为 Docker daemon 可见的宿主机路径。"""
        container_root = self.settings.judge_work_dir.replace("\\", "/").rstrip("/")
        host_root = self.settings.judge_host_work_dir.replace("\\", "/").rstrip("/")
        normalized = container_path.replace("\\", "/")
        if container_root and host_root and (
            normalized == container_root or normalized.startswith(f"{container_root}/")
        ):
            relative = normalized[len(container_root):].lstrip("/")
            return f"{host_root}/{relative}" if relative else host_root
        return container_path

    def _generate_conn_file(self, record_id: int) -> tuple[str, dict]:
        from jupyter_client import write_connection_file

        tmp_dir = self._kernel_path("kernels")
        os.makedirs(tmp_dir, exist_ok=True)
        conn_path = os.path.join(tmp_dir, f"kernel-rec-{record_id}.json")
        key = secrets.token_hex(24).encode("ascii")
        write_connection_file(conn_path, ip="0.0.0.0", key=key)
        with open(conn_path) as f:
            conn_info = json.load(f)
        conn_info["ip"] = "0.0.0.0"
        with open(conn_path, "w") as f:
            json.dump(conn_info, f)
        # Kernel sandbox 以 UID 1000 运行；文件仍以 :ro 挂载，但必须可读。
        os.chmod(conn_path, 0o644)
        return conn_path, conn_info

    def _write_session_redis(self, record_id: int, session: KernelSession):
        """写 Redis session 元数据"""
        try:
            import redis
            r = redis.from_url(self.settings.redis_url)
            r.setex(
                f"kernel:session:{record_id}", 3600,
                json.dumps(session.to_redis_dict()),
            )
        except Exception as e:
            raise RuntimeError(f"Redis 写入失败: {e}") from e

    def _read_session_redis(self, record_id: int) -> KernelSession | None:
        try:
            import redis
            r = redis.from_url(self.settings.redis_url)
            data_str = r.get(f"kernel:session:{record_id}")
            if data_str:
                return KernelSession.from_redis_dict(record_id, json.loads(data_str))
        except Exception:
            logger.debug("Redis 读取 kernel session %d 失败", record_id, exc_info=True)
        return None

    def is_template_initialized(self, record_id: int, version_id: int) -> bool:
        """检查 template version 是否已初始化"""
        try:
            import redis
            r = redis.from_url(self.settings.redis_url)
            marker = r.get(f"kernel:init:{record_id}")
            if marker:
                return int(marker) == version_id
        except Exception:
            logger.debug("Redis 读取 kernel init 标记 %d 失败", record_id, exc_info=True)
        session = self._sessions.get(record_id)
        return (session is not None and
                session.initialized_template_version_id == version_id)

    def mark_template_initialized(self, record_id: int, version_id: int):
        """标记 template version 已初始化（Redis + 内存）"""
        session = self._sessions.get(record_id)
        if not session:
            raise RuntimeError(f"Kernel session {record_id} 不可用")

        previous_version_id = session.initialized_template_version_id
        try:
            import redis
            r = redis.from_url(self.settings.redis_url)
            r.setex(f"kernel:init:{record_id}", 3600, str(version_id))
            session.initialized_template_version_id = version_id
            self._write_session_redis(record_id, session)
        except Exception as exc:
            session.initialized_template_version_id = previous_version_id
            try:
                r.delete(f"kernel:init:{record_id}")
            except Exception:
                logger.warning("Redis 删除 kernel init 标记 %d 失败", record_id, exc_info=True)
            raise RuntimeError(f"Kernel 初始化标记持久化失败: {exc}") from exc

    def create_session(self, record_id: int, lesson_storage_dir: str) -> KernelSession:
        container_name = self._make_container_name(record_id)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

        conn_path, conn_info = self._generate_conn_file(record_id)

        work_dir = self._kernel_path("workspaces", f"student_{record_id}")
        os.makedirs(work_dir, exist_ok=True)
        host_conn_path = self._docker_host_path(conn_path)
        host_work_dir = self._docker_host_path(work_dir)

        # OpenBLAS 默认按宿主机核数创建线程（如 20 线程），与 ipykernel 自身线程、
        # docker exec 进程竞争 pids-limit，曾导致 "pthread_create failed" 后容器
        # 半死、exec 报 "procReady not received"。故限制 BLAS 线程数并放宽 PID 限额。
        cmd = [
            "docker", "run", "-d", "--name", container_name,
            "--network", "none",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp:exec,size=64m",
            "--cpus", "1", "--memory", "256m", "--pids-limit", "256",
            "-e", "OPENBLAS_NUM_THREADS=4",
            "-e", "OMP_NUM_THREADS=4",
            "-e", "MKL_NUM_THREADS=4",
            "-l", f"dai.record_id={record_id}",
            "-v", f"{host_conn_path}:/tmp/conn.json:ro",
            "-v", f"{host_work_dir}:/work:rw",
        ]
        if os.path.isdir(lesson_storage_dir):
            cmd.extend(["-v", f"{lesson_storage_dir}:/course:ro"])
        cmd.extend(["dai-kernel-python:latest", "python", "-m", "ipykernel_launcher", "-f", "/tmp/conn.json"])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Docker 启动失败: {result.stderr}")

        time.sleep(4)
        for _ in range(10):
            alive = subprocess.run(
                ["docker", "ps", "-q", "-f", f"name={container_name}"],
                capture_output=True, text=True,
            )
            if alive.stdout.strip():
                break
            time.sleep(1)
        else:
            raise RuntimeError("Kernel 容器未存活")

        # 容器 alive ≠ 容器可执行：ipykernel 启动（导入 numpy/pandas 等）期间
        # docker exec 会报 "procReady not received"。轮询探测 exec 可用后再返回，
        # runner 内部另有 wait_for_ready(10s) 等待 kernel 就绪。
        for _ in range(15):
            probe = subprocess.run(
                ["docker", "exec", container_name, "python", "-c", "import os"],
                capture_output=True, text=True,
            )
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
            )
            raise RuntimeError("Kernel 容器 exec 探测超时")

        session = KernelSession(record_id, container_name, conn_info,
                                lesson_storage_dir=lesson_storage_dir)
        try:
            self._write_session_redis(record_id, session)
        except Exception:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
            )
            raise
        self._sessions[record_id] = session
        return session

    def get_or_create_session(self, record_id: int, lesson_storage_dir: str = "") -> KernelSession:
        session = self._sessions.get(record_id)
        if session and session.is_alive:
            session.last_active_at = time.time()
            return session

        session = self._read_session_redis(record_id)
        if session:
            alive = subprocess.run(
                ["docker", "ps", "-q", "-f", f"name={session.container_name}"],
                capture_output=True, text=True,
            )
            if alive.stdout.strip():
                self._sessions[record_id] = session
                return session
            else:
                try:
                    import redis
                    r = redis.from_url(self.settings.redis_url)
                    r.delete(f"kernel:session:{record_id}")
                except Exception:
                    logger.warning("Redis 删除旧 kernel session %d 失败", record_id, exc_info=True)

        return self.create_session(record_id, lesson_storage_dir)

    def execute(self, record_id: int, code: str) -> dict:
        """通过 docker exec + trusted runner 在持久 ipykernel 中执行代码"""
        session = self._sessions.get(record_id)
        if not session or not session.is_alive:
            raise RuntimeError(f"Kernel session {record_id} 不可用")

        # Redis 互斥锁（fail closed）
        import redis
        lock_key = f"kernel:lock:{record_id}"
        lock_token = self._make_lock_token()
        try:
            r = redis.from_url(self.settings.redis_url)
            acquired = r.set(lock_key, lock_token, nx=True, ex=60)
            if not acquired:
                raise RuntimeError("Kernel 正忙，请等待当前代码执行完成")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Redis 不可用，无法获取执行锁: {e}") from e

        try:
            # docker exec 运行 trusted runner，代码通过 stdin JSON 传入
            exec_cmd = [
                "docker", "exec", "-i", session.container_name,
                "python", RUNNER_PATH,
            ]
            start = time.perf_counter()
            try:
                result = subprocess.run(
                    exec_cmd,
                    input=json.dumps({"code": code}),
                    capture_output=True, text=True,
                    timeout=KERNEL_HARD_TIMEOUT,
                )
                elapsed_ms = int((time.perf_counter() - start) * 1000)
            except subprocess.TimeoutExpired:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                # 保存旧 session 信息
                old_storage = session.lesson_storage_dir
                # 销毁旧容器
                self.destroy(record_id)
                # 立即重建
                try:
                    self.create_session(record_id, old_storage)
                except Exception as rebuild_err:
                    raise RuntimeError(
                        f"代码执行超时（>{KERNEL_HARD_TIMEOUT}s），重建 kernel 失败: {rebuild_err}"
                    ) from rebuild_err
                raise RuntimeError(
                    f"代码执行超时（>{KERNEL_HARD_TIMEOUT}s），kernel 已重建"
                )

            if result.returncode != 0:
                runner_error = (result.stderr or result.stdout or "unknown runner error").strip()
                raise RuntimeError(f"Kernel runner 执行失败: {runner_error}")

            # 解析 runner 输出
            outputs = []
            try:
                data = json.loads(result.stdout.strip() or "{}")
                if data.get("error"):
                    outputs.append({"msg_type": "error", "content": {"text": data["error"]}})
                for o in data.get("outputs", []):
                    outputs.append(o)
            except json.JSONDecodeError:
                if result.stdout:
                    outputs.append({"msg_type": "stream", "content": {"name": "stdout", "text": result.stdout}})
                if result.stderr:
                    outputs.append({"msg_type": "stream", "content": {"name": "stderr", "text": result.stderr}})

            return {"outputs": outputs, "execution_time_ms": elapsed_ms}

        finally:
            # token-safe unlock
            try:
                r = redis.from_url(self.settings.redis_url)
                r.eval(
                    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                    1, lock_key, lock_token,
                )
            except Exception:
                logger.debug("锁释放失败或已过期 record_id=%d", record_id, exc_info=True)
            session.last_active_at = time.time()

    def interrupt(self, record_id: int):
        session = self._sessions.get(record_id)
        if session and session.is_alive:
            subprocess.run(
                ["docker", "exec", session.container_name, "kill", "-INT", "1"],
                capture_output=True,
            )

    def restart(self, record_id: int, lesson_storage_dir: str = "") -> KernelSession:
        if not lesson_storage_dir:
            existing = self._sessions.get(record_id)
            if existing:
                lesson_storage_dir = existing.lesson_storage_dir
        self.destroy(record_id)
        return self.create_session(record_id, lesson_storage_dir)

    def destroy(self, record_id: int):
        session = self._sessions.pop(record_id, None)
        if session:
            subprocess.run(
                ["docker", "rm", "-f", session.container_name],
                capture_output=True,
            )
        try:
            import redis
            r = redis.from_url(self.settings.redis_url)
            r.delete(f"kernel:session:{record_id}")
            r.delete(f"kernel:init:{record_id}")
        except Exception:
            logger.warning("Redis 删除 kernel 记录 %d 失败", record_id, exc_info=True)

    def cleanup_idle(self, max_idle_seconds: int = 900):
        now = time.time()
        for rid, session in list(self._sessions.items()):
            if now - session.last_active_at > max_idle_seconds:
                self.destroy(rid)

    def recover_from_docker(self):
        """从 Docker label dai.record_id 恢复所有未记录的 session，重建 Redis 元数据"""
        result = subprocess.run(
            ["docker", "ps", "-q", "--filter", "label=dai.record_id"],
            capture_output=True, text=True,
        )
        container_ids = result.stdout.strip().split()
        for cid in container_ids:
            if not cid:
                continue
            try:
                name_result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.Name}}", cid],
                    capture_output=True, text=True,
                )
                container_name = name_result.stdout.strip().lstrip("/")
                if not container_name or not container_name.startswith("dai-kernel-rec-"):
                    continue

                label_result = subprocess.run(
                    ["docker", "inspect", "-f", '{{index .Config.Labels "dai.record_id"}}', cid],
                    capture_output=True, text=True,
                )
                try:
                    record_id = int(label_result.stdout.strip())
                except ValueError:
                    continue

                if record_id in self._sessions:
                    continue

                # 从容器内读 conn file
                conn_info = None
                cp_result = subprocess.run(
                    ["docker", "exec", cid, "cat", "/tmp/conn.json"],
                    capture_output=True, text=True, timeout=5,
                )
                if cp_result.returncode == 0:
                    try:
                        conn_info = json.loads(cp_result.stdout)
                    except json.JSONDecodeError:
                        pass

                if not conn_info:
                    # fallback: try Redis
                    session = self._read_session_redis(record_id)
                    if session:
                        conn_info = session.conn_info

                if conn_info:
                    session = KernelSession(record_id, container_name, conn_info)
                    self._sessions[record_id] = session
                    # 重建 Redis 元数据
                    try:
                        self._write_session_redis(record_id, session)
                    except Exception:
                        logger.warning("恢复 kernel session %d Redis 写入失败", record_id, exc_info=True)
                    logger.info("Recovered kernel session %d from Docker label", record_id)
            except Exception as e:
                logger.warning("Failed to recover container %s: %s", cid, e)


_kernel_manager: Optional[KernelManager] = None


def get_kernel_manager() -> KernelManager:
    global _kernel_manager
    if _kernel_manager is None:
        _kernel_manager = KernelManager()
    return _kernel_manager
