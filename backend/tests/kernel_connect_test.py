"""简单的 Kernel 连接测试 - 使用 host 网络模式"""
import json, secrets, socket, subprocess, time, sys, os

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")
CONN_FILE = os.path.join(os.environ.get("TEMP", "/tmp"), "kernel-simple-test.json")

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

# 1. 生成 connection file
cfg = {
    "shell_port": free_port(),
    "iopub_port": free_port(),
    "stdin_port": free_port(),
    "control_port": free_port(),
    "hb_port": free_port(),
    "ip": "0.0.0.0",
    "key": secrets.token_hex(24),
    "transport": "tcp",
    "signature_scheme": "hmac-sha256",
    "kernel_name": "",
}
with open(CONN_FILE, "w") as f:
    json.dump(cfg, f)
print(f"Connection file: {CONN_FILE}")
print(f"Ports: shell={cfg['shell_port']} iopub={cfg['iopub_port']} stdin={cfg['stdin_port']} control={cfg['control_port']} hb={cfg['hb_port']}")

# 2. 构建 docker run 命令（host 网络 + 端口映射）
container_name = "dai-kernel-simple"
subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

cmd = [
    "docker", "run", "-d", "--name", container_name,
    "--network", "host",
    "-v", f"{CONN_FILE}:/tmp/kernel-conn.json:ro",
    "dai-kernel-python:latest",
    "python", "-m", "ipykernel_launcher", "-f", "/tmp/kernel-conn.json",
]
print(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)
print(f"Container: {result.stdout.strip()}")

time.sleep(4)

# 3. 检查容器
result = subprocess.run(["docker", "logs", container_name], capture_output=True, text=True)
print(f"Logs: {result.stdout.strip()[-300:]}")

result = subprocess.run(["docker", "ps", "-q", "-f", f"name={container_name}"], capture_output=True, text=True)
if not result.stdout.strip():
    print("ERROR: Container not running!")
    sys.exit(1)
print("Container is running")

# 4. 连接 kernel
print("\n=== Connecting to kernel ===")
# 使用 python 子进程运行连接代码
connect_code = f'''
import json
with open(r"{CONN_FILE}") as f:
    conn = json.load(f)
conn["ip"] = "127.0.0.1"
conn["kernel_name"] = ""
from jupyter_client import BlockingKernelClient
kc = BlockingKernelClient(**{{k: v for k, v in conn.items()
    if k in ("shell_port","iopub_port","stdin_port","hb_port","control_port","ip","key","transport","signature_scheme","kernel_name")}})
try:
    kc.start_channels()
    kc.wait_for_ready(timeout=10)
    print("Kernel ready!")
    reply = kc.execute_interactive("print(42+42)")
    for msg in reply:
        if msg.get("msg_type") == "stream":
            print("Output:", msg["content"]["text"].strip())
    kc.stop_channels()
    print("SUCCESS")
except Exception as e:
    print(f"FAIL: {{e}}")
    import traceback; traceback.print_exc()
'''

result = subprocess.run([PYTHON, "-c", connect_code], capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[-500:])

# 5. 清理
print("\n=== Cleanup ===")
subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
os.remove(CONN_FILE)
print("Done")
