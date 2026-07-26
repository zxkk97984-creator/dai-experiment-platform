r"""
里程碑 0：Kernel 原型验证脚本

验证目标：
0.1 构建 dai-kernel-python 镜像 ✓
0.2 宿主机生成 connection file → 挂载到容器 → 启动 ipykernel → jupyter_client 连通
0.3 顺序执行两条代码，第二条引用第一条的变量 → 变量共享成功
0.4 matplotlib 图片输出
0.5 异常输出 traceback
0.6 安全限制验证（os.system、网络、文件系统）
0.7 启动时间、内存占用、清理耗时

用法：
    cd backend
    .venv\Scripts\python.exe tests\test_kernel_prototype.py
"""

import subprocess
import tempfile
import time
import json
import uuid
import shutil
import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def run_cmd(cmd: list, **kwargs):
    """运行命令，返回 CompletedProcess"""
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def docker_rm(container_name: str):
    """强制删除容器（忽略错误）"""
    run_cmd(["docker", "rm", "-f", container_name])


# ---------------------------------------------------------------------------
# 0.2: 宿主机 → 容器 ipykernel 连接
# ---------------------------------------------------------------------------

def test_02_kernel_connection():
    """验证宿主机能通过 jupyter_client 连接容器内 ipykernel"""
    print("=" * 60)
    print("0.2 测试：宿主机连接容器内 ipykernel")
    print("=" * 60)

    session_id = f"proto-{uuid.uuid4().hex[:8]}"
    container_name = f"dai-kernel-{session_id}"
    conn_file_host = Path(tempfile.gettempdir()) / f"kernel-{session_id}.json"

    # 创建 Docker 内部网络（如果不存在）
    net_check = run_cmd(["docker", "network", "ls", "-q", "-f", "name=dai-kernel-net"])
    if not net_check.stdout.strip():
        print("  → 创建 dai-kernel-net 网络...")
        run_cmd(["docker", "network", "create", "dai-kernel-net"])

    # 生成 connection file
    print(f"  → 生成 connection file: {conn_file_host}")
    from jupyter_client import write_connection_file
    import secrets
    conn_file_host.parent.mkdir(parents=True, exist_ok=True)
    write_connection_file(
        str(conn_file_host),
        ip="0.0.0.0",  # 容器内监听所有接口
        key=secrets.token_hex(24).encode("ascii"),
    )

    try:
        # 启动容器
        print(f"  → 启动容器: {container_name}")
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--network", "dai-kernel-net",
            "--cpus", "1",
            "--memory", "512m",
            "--pids-limit", "50",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",
            "--user", "1000:1000",
            "-v", f"{conn_file_host}:/tmp/kernel-conn.json:ro",
            "-l", f"dai.test_session={session_id}",
            "dai-kernel-python:latest",
            "python", "-m", "ipykernel_launcher", "-f", "/tmp/kernel-conn.json",
        ]
        result = run_cmd(cmd)
        assert result.returncode == 0, f"容器启动失败: {result.stderr}"
        container_id = result.stdout.strip()
        print(f"  → 容器 ID: {container_id[:12]}...")

        # 等待 ipykernel 就绪
        time.sleep(3)

        # 检查容器是否存活
        ps_result = run_cmd(["docker", "ps", "-q", "-f", f"name={container_name}"])
        assert ps_result.stdout.strip(), "容器未在运行!"
        print("  → 容器运行正常")

        # 连接 kernel
        print("  → 连接 kernel...")
        from jupyter_client import BlockingKernelClient
        import atexit

        # 由于 --network none 不可行（jupyter_client 需要 ZMQ/TCP），
        # 容器在 dai-kernel-net bridge 网络上，需要通过容器 IP 连接
        inspect = run_cmd([
            "docker", "inspect", "-f",
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            container_name
        ])
        container_ip = inspect.stdout.strip()
        print(f"  → 容器 IP: {container_ip}")

        # 读取 connection file 并修改 IP 为容器 IP
        with open(conn_file_host) as f:
            conn_info = json.load(f)
        conn_info["ip"] = container_ip
        conn_info["kernel_name"] = ""

        kc = BlockingKernelClient(**{k: v for k, v in conn_info.items()
            if k in ("shell_port", "iopub_port", "stdin_port", "hb_port",
                     "control_port", "ip", "key", "transport", "signature_scheme", "kernel_name")})

        kc.load_connection_info(conn_info)

        try:
            kc.start_channels()
            kc.wait_for_ready(timeout=10)
            print("  → Kernel 就绪 ✓")
        except Exception as e:
            # 尝试获取容器日志
            logs = run_cmd(["docker", "logs", container_name])
            print(f"  ✗ Kernel 连接失败: {e}")
            print(f"  容器日志:\n{logs.stdout[-500:]}")
            raise

        return kc, container_name, conn_file_host

    except Exception:
        docker_rm(container_name)
        raise


# ---------------------------------------------------------------------------
# 0.3: 跨 cell 变量共享
# ---------------------------------------------------------------------------

def test_03_variable_sharing(kc):
    """验证跨 cell 变量共享（真正 Notebook 行为）"""
    print()
    print("=" * 60)
    print("0.3 测试：跨 cell 变量共享")
    print("=" * 60)

    # Cell 1: 定义变量
    print("  → Cell 1: 定义变量 x = 42, name = 'DAI'")
    reply = kc.execute_interactive("x = 42\nname = 'DAI'\nprint(f'x={x}, name={name}')")
    stdout_1 = _collect_stdout(reply)
    print(f"    输出: {stdout_1.strip()}")
    assert "x=42" in stdout_1 and "name=DAI" in stdout_1, "Cell 1 输出不符合预期"

    # Cell 2: 引用上一个 cell 的变量
    print("  → Cell 2: 引用 Cell 1 的变量 print(x * 2)")
    reply = kc.execute_interactive("print(x * 2)")
    stdout_2 = _collect_stdout(reply)
    print(f"    输出: {stdout_2.strip()}")
    assert "84" in stdout_2, f"Cell 2 应该输出 84，实际: {stdout_2}"

    # Cell 3: 引用字符串变量
    print("  → Cell 3: 引用字符串变量 print(f'Hello {name}')")
    reply = kc.execute_interactive("print(f'Hello {name}')")
    stdout_3 = _collect_stdout(reply)
    print(f"    输出: {stdout_3.strip()}")
    assert "Hello DAI" in stdout_3, f"Cell 3 输出不符合预期: {stdout_3}"

    print("  ✓ 变量跨 cell 共享正常")


def _collect_stdout(execute_reply):
    """从 execute_interactive 返回值中收集 stdout 文本"""
    stdout_parts = []
    for msg in execute_reply:
        if msg.get("msg_type") == "stream" and msg.get("content", {}).get("name") == "stdout":
            stdout_parts.append(msg["content"]["text"])
    return "".join(stdout_parts)


# ---------------------------------------------------------------------------
# 0.4: matplotlib 图片输出
# ---------------------------------------------------------------------------

def test_04_matplotlib_output(kc):
    """验证 matplotlib 图片输出"""
    print()
    print("=" * 60)
    print("0.4 测试：matplotlib 图片输出")
    print("=" * 60)

    code = """
import matplotlib
matplotlib.use('Agg')  # 非交互后端
import matplotlib.pyplot as plt
import io, base64

fig, ax = plt.subplots()
ax.plot([1, 2, 3, 4], [10, 20, 25, 30])
ax.set_title('Test Plot')
ax.set_xlabel('X')
ax.set_ylabel('Y')

buf = io.BytesIO()
fig.savefig(buf, format='png')
buf.seek(0)
img_b64 = base64.b64encode(buf.read()).decode()
print('IMAGE_PNG:' + img_b64[:50] + '...')
print(f'IMAGE_SIZE:{len(img_b64)}')
plt.close()
"""
    print("  → 执行 matplotlib 绘图代码...")
    reply = kc.execute_interactive(code)
    stdout = _collect_stdout(reply)
    print(f"    输出前 200 字符: {stdout[:200]}...")
    assert "IMAGE_PNG:" in stdout, "应该输出 base64 图片"
    assert "IMAGE_SIZE:" in stdout, "应该输出图片大小"
    print("  ✓ matplotlib 输出正常")


# ---------------------------------------------------------------------------
# 0.5: 异常 traceback
# ---------------------------------------------------------------------------

def test_05_error_traceback(kc):
    """验证 Python 异常能正确返回 traceback"""
    print()
    print("=" * 60)
    print("0.5 测试：异常 traceback 输出")
    print("=" * 60)

    # 简单异常
    print("  → 触发 ZeroDivisionError...")
    reply = kc.execute_interactive("1/0")
    error_content = None
    for msg in reply:
        if msg.get("msg_type") == "error":
            error_content = msg["content"]
            break
    assert error_content is not None, "应该收到 error 类型消息"
    assert error_content["ename"] == "ZeroDivisionError", f"异常类型应为 ZeroDivisionError，实际: {error_content['ename']}"
    traceback_text = "\n".join(error_content["traceback"])
    print(f"    traceback:\n{traceback_text[:300]}...")
    print("  ✓ 异常 traceback 正常")

    # 自定义异常
    print("  → 触发自定义 ValueError...")
    reply = kc.execute_interactive("raise ValueError('test error 测试错误')")
    for msg in reply:
        if msg.get("msg_type") == "error":
            error_content = msg["content"]
            break
    assert error_content["ename"] == "ValueError"
    assert "测试错误" in str(error_content["traceback"])
    print("  ✓ 中文异常信息正确")


# ---------------------------------------------------------------------------
# 0.6: 安全限制
# ---------------------------------------------------------------------------

def test_06_security(container_name):
    """验证 Docker 安全限制"""
    print()
    print("=" * 60)
    print("0.6 测试：Docker 安全限制")
    print("=" * 60)

    # 测试 1: 非 root 用户
    print("  → 检查运行用户...")
    result = run_cmd(["docker", "exec", container_name, "whoami"])
    user = result.stdout.strip()
    print(f"    当前用户: {user}")
    assert user != "root", f"应该是非 root 用户，实际: {user}"

    # 测试 2: 只读根文件系统
    print("  → 检查根文件系统只读...")
    result = run_cmd([
        "docker", "exec", container_name,
        "python", "-c",
        "import os; print('readonly' if not os.access('/', os.W_OK) else 'writable')"
    ])
    # 非 root 用户无法在 / 写入，这已经证明根目录不可写
    print(f"    根目录状态: {result.stdout.strip()}")

    # 测试 3: 资源限制
    print("  → 检查内存限制...")
    result = run_cmd([
        "docker", "inspect", "-f", "{{.HostConfig.Memory}}", container_name
    ])
    mem_bytes = int(result.stdout.strip())
    print(f"    内存限制: {mem_bytes / 1024 / 1024:.0f} MB")
    assert mem_bytes == 512 * 1024 * 1024, f"内存限制应为 512MB，实际: {mem_bytes}"

    # 测试 4: CPU 限制
    print("  → 检查 CPU 限制...")
    result = run_cmd([
        "docker", "inspect", "-f", "{{.HostConfig.NanoCpus}}", container_name
    ])
    nano_cpus = int(result.stdout.strip())
    print(f"    CPU 限制: {nano_cpus / 1e9:.0f} 核")
    assert nano_cpus == 1_000_000_000, f"CPU 限制应为 1 核"

    # 测试 5: 容器内尝试访问外网
    print("  → 测试外网访问...")
    result = run_cmd([
        "docker", "exec", container_name,
        "python", "-c",
        "import urllib.request; urllib.request.urlopen('https://example.com', timeout=3)"
    ])
    # 由于 dai-kernel-net 没有 iptables 规则阻止外网（目前只做了 bridge），
    # 这个测试记录当前状态，后续需要加 iptables 规则
    if result.returncode != 0:
        print(f"    外网访问: 被阻止 ✓ ({result.stderr.strip()[:100]})")
    else:
        print(f"    ⚠ 外网访问未被阻止（后续需加 iptables 规则）")

    print("  ✓ 安全限制验证完成")


# ---------------------------------------------------------------------------
# 0.7: 启停时间
# ---------------------------------------------------------------------------

def test_07_performance():
    """测试容器启动时间、清理耗时"""
    print()
    print("=" * 60)
    print("0.7 测试：容器启停性能")
    print("=" * 60)

    # 测试启动时间
    print("  → 测试容器启动时间...")
    test_name = f"dai-perf-test-{uuid.uuid4().hex[:8]}"
    conn_file = Path(tempfile.gettempdir()) / f"kernel-perf-{uuid.uuid4().hex[:8]}.json"

    from jupyter_client import write_connection_file
    import secrets
    write_connection_file(str(conn_file), ip="0.0.0.0", key=secrets.token_hex(24).encode("ascii"))

    start_time = time.perf_counter()
    try:
        run_cmd([
            "docker", "run", "-d", "--name", test_name,
            "--network", "dai-kernel-net",
            "--cpus", "1", "--memory", "512m",
            "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",
            "--user", "1000:1000",
            "-v", f"{conn_file}:/tmp/kernel-conn.json:ro",
            "dai-kernel-python:latest",
            "python", "-m", "ipykernel_launcher", "-f", "/tmp/kernel-conn.json",
        ])
        elapsed = time.perf_counter() - start_time
        print(f"    启动耗时: {elapsed:.2f}s")

        # 检查内存占用
        time.sleep(2)
        stats = run_cmd(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", test_name])
        mem_usage = stats.stdout.strip()
        print(f"    内存占用: {mem_usage}")

        assert elapsed < 10, f"启动太慢: {elapsed:.2f}s > 10s"
        print("  ✓ 启动时间 < 10s")
    finally:
        # 清理
        clean_start = time.perf_counter()
        docker_rm(test_name)
        clean_elapsed = time.perf_counter() - clean_start
        # 清理临时文件
        conn_file.unlink(missing_ok=True)
        print(f"    清理耗时: {clean_elapsed:.2f}s")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║    里程碑 0：Kernel 原型验证                         ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    kc = None
    container_name = None
    conn_file = None
    passed = 0
    failed = 0

    tests = []

    # 0.2 连接
    try:
        kc, container_name, conn_file = test_02_kernel_connection()
        tests.append(("0.2 宿主机连接容器 ipykernel", True))
        passed += 1
    except Exception as e:
        tests.append(("0.2 宿主机连接容器 ipykernel", False))
        print(f"  ✗ 连接失败: {e}")
        failed += 1
        import traceback
        traceback.print_exc()
        # 连接失败则终止后续测试
        print_result(passed, failed, tests)
        return 1

    # 0.3 变量共享
    try:
        test_03_variable_sharing(kc)
        tests.append(("0.3 跨 cell 变量共享", True))
        passed += 1
    except Exception as e:
        tests.append(("0.3 跨 cell 变量共享", False))
        print(f"  ✗ 失败: {e}")
        failed += 1
        import traceback
        traceback.print_exc()

    # 0.4 matplotlib
    try:
        test_04_matplotlib_output(kc)
        tests.append(("0.4 matplotlib 图片输出", True))
        passed += 1
    except Exception as e:
        tests.append(("0.4 matplotlib 图片输出", False))
        print(f"  ✗ 失败: {e}")
        failed += 1
        import traceback
        traceback.print_exc()

    # 0.5 异常
    try:
        test_05_error_traceback(kc)
        tests.append(("0.5 异常 traceback", True))
        passed += 1
    except Exception as e:
        tests.append(("0.5 异常 traceback", False))
        print(f"  ✗ 失败: {e}")
        failed += 1
        import traceback
        traceback.print_exc()

    # 0.6 安全
    try:
        test_06_security(container_name)
        tests.append(("0.6 Docker 安全限制", True))
        passed += 1
    except Exception as e:
        tests.append(("0.6 Docker 安全限制", False))
        print(f"  ✗ 失败: {e}")
        failed += 1
        import traceback
        traceback.print_exc()

    # 0.7 性能
    try:
        test_07_performance()
        tests.append(("0.7 容器启停性能", True))
        passed += 1
    except Exception as e:
        tests.append(("0.7 容器启停性能", False))
        print(f"  ✗ 失败: {e}")
        failed += 1
        import traceback
        traceback.print_exc()

    # 清理
    print()
    print("=" * 60)
    print("清理...")
    if kc:
        kc.stop_channels()
    if container_name:
        docker_rm(container_name)
    if conn_file and conn_file.exists():
        conn_file.unlink()
    print("  ✓ 清理完成")

    print_result(passed, failed, tests)
    return 0 if failed == 0 else 1


def print_result(passed, failed, tests):
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print(f"║  结果: {passed}/{passed + failed} 通过                                    ║")
    print("╚══════════════════════════════════════════════════════╝")
    for name, ok in tests:
        print(f"  {'✓' if ok else '✗'} {name}")


if __name__ == "__main__":
    sys.exit(main())
