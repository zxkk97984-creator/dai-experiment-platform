"""
Kernel Session 管理器

管理 Docker 容器中的 ipykernel 实例，提供代码执行、中断、重启功能。
关键设计：
- connection file 在容器内生成，宿主机通过 docker cp 获取（避免 Docker Desktop WSL2 路径问题）
- 使用 Redis 记录 session 状态，支持后端重启恢复
- 每 record_id 一把 Redis 互斥锁
"""
import json
import os
import subprocess
import time
from typing import Optional

from app.config import Settings, get_settings


class KernelSession:
    """单个 kernel session 的运行时状态"""

    def __init__(self, record_id: int, container_name: str, conn_info: dict):
        self.record_id = record_id
        self.container_name = container_name
        self.conn_info = conn_info
        self.last_active_at = time.time()

    @property
    def is_alive(self) -> bool:
        """检查容器是否存活"""
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name={self.container_name}"],
            capture_output=True, text=True,
        )
        return bool(result.stdout.strip())


class KernelManager:
    """管理所有 kernel session 的生命周期"""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._sessions: dict[int, KernelSession] = {}
        self._lock_key_prefix = "kernel:lock"

    def _make_container_name(self, record_id: int) -> str:
        return f"dai-kernel-rec-{record_id}"

    def _generate_conn_info(self, record_id: int) -> tuple[str, dict]:
        """在宿主机生成 connection file，返回 (file_path, conn_info)"""
        from jupyter_client import write_connection_file
        import secrets

        tmp_dir = os.path.join(os.environ.get("TEMP", "/tmp"), "dai-kernels")
        os.makedirs(tmp_dir, exist_ok=True)
        conn_path = os.path.join(tmp_dir, f"kernel-rec-{record_id}.json")
        key = secrets.token_hex(24).encode("ascii")
        write_connection_file(conn_path, ip="0.0.0.0", key=key)
        # 读取并确保 ip（debug 日志）
        with open(conn_path) as f:
            conn_info = json.load(f)
        print(f"[DEBUG kernel_manager] wrote conn file: ip={conn_info.get('ip')} ports={conn_info.get('shell_port')}", flush=True)
        if conn_info.get("ip") != "0.0.0.0":
            print(f"[DEBUG kernel_manager] WARNING: ip was {conn_info['ip']}, fixing to 0.0.0.0", flush=True)
            conn_info["ip"] = "0.0.0.0"
            with open(conn_path, "w") as f:
                json.dump(conn_info, f)
        return conn_path, conn_info

    def create_session(self, record_id: int, lesson_storage_dir: str) -> KernelSession:
        """创建新 kernel session。宿主机生成连接文件 → 挂载到容器 → 端口映射。"""
        container_name = self._make_container_name(record_id)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

        # 宿主机生成连接文件
        conn_path, conn_info = self._generate_conn_info(record_id)
        ports = [conn_info[k] for k in ("shell_port","iopub_port","stdin_port","control_port","hb_port")]

        work_dir = os.path.join(os.environ.get("TEMP", "/tmp"), "dai-workspaces", f"student_{record_id}")
        os.makedirs(work_dir, exist_ok=True)

        cmd = [
            "docker", "run", "-d", "--name", container_name,
            "--cpus", "1", "--memory", "512m", "--pids-limit", "50",
            "-l", f"dai.record_id={record_id}",
            "-v", f"{conn_path}:/tmp/conn.json:ro",
            "-v", f"{work_dir}:/work",
        ]
        for p in ports:
            cmd.extend(["-p", f"127.0.0.1:{p}:{p}"])
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
            raise RuntimeError(f"Kernel 容器未存活")

        conn_info["ip"] = "127.0.0.1"
        session = KernelSession(record_id, container_name, conn_info)
        self._sessions[record_id] = session
        return session

    def get_or_create_session(self, record_id: int, lesson_storage_dir: str = "") -> KernelSession:
        """获取已有 session 或创建新 session"""
        # 1. 检查内存缓存
        session = self._sessions.get(record_id)
        if session and session.is_alive:
            session.last_active_at = time.time()
            return session

        # 2. 检查 Redis 中是否有记录
        try:
            import redis
            r = redis.from_url(self.settings.redis_url)
            data_str = r.get(f"kernel:session:{record_id}")
            if data_str:
                data = json.loads(data_str)
                container_name = data["container_name"]
                alive = subprocess.run(
                    ["docker", "ps", "-q", "-f", f"name={container_name}"],
                    capture_output=True, text=True,
                )
                if alive.stdout.strip():
                    session = KernelSession(record_id, container_name, data["conn_info"])
                    self._sessions[record_id] = session
                    return session
                else:
                    r.delete(f"kernel:session:{record_id}")
        except Exception:
            pass

        # 3. 创建新 session
        return self.create_session(record_id, lesson_storage_dir)

    def execute(self, record_id: int, code: str) -> dict:
        """
        在指定 session 中执行代码，返回 {outputs: [...], execution_time_ms: int}

        使用 Redis 互斥锁（如果可用）保证同一 kernel 串行执行。
        """
        session = self._sessions.get(record_id)
        if not session or not session.is_alive:
            raise RuntimeError(f"Kernel session {record_id} 不可用")

        # 尝试获取锁
        lock_key = f"{self._lock_key_prefix}:{record_id}"
        lock = None
        try:
            import redis
            r = redis.from_url(self.settings.redis_url)
            lock = r.set(lock_key, "1", nx=True, ex=60)
            if not lock:
                raise RuntimeError("Kernel 正忙，请等待当前代码执行完成")
        except Exception:
            pass

        try:
            # 连接到 kernel 并执行
            conn_info = dict(session.conn_info)
            conn_info["kernel_name"] = ""

            from jupyter_client import BlockingKernelClient
            kc = BlockingKernelClient()
            kc.load_connection_info(conn_info)

            start = time.perf_counter()
            kc.start_channels()
            kc.wait_for_ready(timeout=10)

            msg_id = kc.execute(code)
            outputs = []
            while True:
                try:
                    msg = kc.get_iopub_msg(timeout=self.settings.judge_timeout_seconds or 30)
                    mt = msg.get("msg_type", "")
                    if mt == "status":
                        if msg["content"].get("execution_state") == "idle":
                            break
                    elif mt in ("stream", "display_data", "execute_result", "error"):
                        content = dict(msg["content"])
                        # 将 bytes 转为可 JSON 序列化
                        if "data" in content:
                            content["data"] = {
                                k: (v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v)
                                for k, v in content["data"].items()
                            }
                        outputs.append({"msg_type": mt, "content": content})
                except Exception:
                    break

            kc.stop_channels()
            elapsed = int((time.perf_counter() - start) * 1000)

            return {"outputs": outputs, "execution_time_ms": elapsed}

        finally:
            if lock:
                try:
                    import redis
                    r = redis.from_url(self.settings.redis_url)
                    r.delete(lock_key)
                except Exception:
                    pass
            session.last_active_at = time.time()

    def interrupt(self, record_id: int):
        """中断当前 kernel 执行"""
        session = self._sessions.get(record_id)
        if session and session.is_alive:
            subprocess.run(
                ["docker", "exec", session.container_name, "kill", "-INT", "1"],
                capture_output=True,
            )

    def restart(self, record_id: int, lesson_storage_dir: str = "") -> KernelSession:
        """重启 kernel（销毁旧容器，创建新的）"""
        self.destroy(record_id)
        return self.create_session(record_id, lesson_storage_dir)

    def destroy(self, record_id: int):
        """销毁 kernel session"""
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
        except Exception:
            pass

    def cleanup_idle(self, max_idle_seconds: int = 1800):
        """清理超过 max_idle_seconds 未使用的 session"""
        now = time.time()
        to_clean = []
        for rid, session in list(self._sessions.items()):
            if now - session.last_active_at > max_idle_seconds:
                to_clean.append(rid)
        for rid in to_clean:
            self.destroy(rid)

    def recover_from_docker(self):
        """从 Docker label 恢复所有未记录的 session"""
        result = subprocess.run(
            ["docker", "ps", "-q", "--filter", "label=dai.record_id"],
            capture_output=True, text=True,
        )
        container_ids = result.stdout.strip().split()
        for cid in container_ids:
            if not cid:
                continue
            labels = subprocess.run(
                ["docker", "inspect", "-f", "{{.Config.Labels}}", cid],
                capture_output=True, text=True,
            )
            # 解析 label 恢复 record_id...（简化实现，后续完善）
            pass


# 全局单例
_kernel_manager: Optional[KernelManager] = None


def get_kernel_manager() -> KernelManager:
    global _kernel_manager
    if _kernel_manager is None:
        _kernel_manager = KernelManager()
    return _kernel_manager
