"""容器内部 Kernel 自连接测试 - 完全在 Python 中完成"""
import json, secrets, socket, subprocess, time, os, sys

WIN_TEMP = os.environ.get("TEMP", "/tmp")
CONN_FILE = os.path.join(WIN_TEMP, "kernel-internal-v2.json")
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")

def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

# 1. 清理旧容器
run("docker rm -f dai-test-v2")

# 2. 创建 connection file
def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]

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
    json.dump(cfg, f, indent=2)
print(f"1. Connection file created: {CONN_FILE}")
print(f"   Ports: shell={cfg['shell_port']} iopub={cfg['iopub_port']} stdin={cfg['stdin_port']} control={cfg['control_port']} hb={cfg['hb_port']}")

# 3. 启动容器
print("\n2. Starting container...")
cmd = f"""docker run -d --name dai-test-v2 --network host -v "{CONN_FILE}:/tmp/kernel-conn.json:ro" dai-kernel-python:latest python -m ipykernel_launcher -f /tmp/kernel-conn.json"""
result = run(cmd)
print(f"   Container: {result.stdout.strip()}")

time.sleep(4)

# 4. 检查状态
status = run("docker ps --filter name=dai-test-v2 --format '{{.Status}}'")
print(f"   Status: {status.stdout.strip()}")

# 5. 看日志
logs = run("docker logs dai-test-v2")
print(f"   Logs (last 5 lines):")
for line in logs.stdout.strip().split("\n")[-5:]:
    print(f"     {line}")

if not status.stdout.strip():
    print("ERROR: Container not running!")
    sys.exit(1)

# 6. 容器内自连接
print("\n3. Testing internal connection (docker exec)...")
connect_code = f'''
import json
with open("/tmp/kernel-conn.json") as f:
    cfg = json.load(f)
cfg["ip"] = "127.0.0.1"
cfg["kernel_name"] = ""
from jupyter_client import BlockingKernelClient
kc = BlockingKernelClient(**{{k:v for k,v in cfg.items()
    if k in ("shell_port","iopub_port","stdin_port","hb_port","control_port","ip","key","transport","signature_scheme","kernel_name")}})
try:
    kc.start_channels()
    kc.wait_for_ready(timeout=10)
    print("KERNEL_OK")
    reply = kc.execute_interactive("print(42+42)")
    for msg in reply:
        if msg.get("msg_type") == "stream":
            print("OUTPUT:" + msg["content"]["text"].strip())
    # 测试变量共享
    kc.execute_interactive("x = 99")
    reply2 = kc.execute_interactive("print(x)")
    for msg in reply2:
        if msg.get("msg_type") == "stream":
            print("SHARED:" + msg["content"]["text"].strip())
    kc.stop_channels()
    print("ALL_OK")
except Exception as e:
    print(f"FAIL: {{e}}")
    import traceback; traceback.print_exc()
'''
# 把代码写入文件然后复制进容器
connect_file = os.path.join(WIN_TEMP, "connect_test.py")
with open(connect_file, "w") as f:
    f.write(connect_code)
result = run(f"docker cp {connect_file} dai-test-v2:/tmp/connect_test.py")
result = run("docker exec dai-test-v2 python3 /tmp/connect_test.py")
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:500])

# 7. Docker 资源检查
print("\n4. Resource check...")
stats = run("docker stats --no-stream --format 'CPU: {{.CPUPerc}} MEM: {{.MemUsage}}' dai-test-v2")
print(f"   {stats.stdout.strip()}")

# 8. 同时从宿主机连接测试
print("\n5. Testing host connection...")
host_connect = f'''
import json
with open(r"{CONN_FILE}") as f:
    cfg = json.load(f)
cfg["ip"] = "127.0.0.1"
cfg["kernel_name"] = ""
from jupyter_client import BlockingKernelClient
kc = BlockingKernelClient(**{{k:v for k,v in cfg.items()
    if k in ("shell_port","iopub_port","stdin_port","hb_port","control_port","ip","key","transport","signature_scheme","kernel_name")}})
try:
    kc.start_channels()
    kc.wait_for_ready(timeout=10)
    print("HOST_OK")
    reply = kc.execute_interactive("print('host_connected')")
    for msg in reply:
        if msg.get("msg_type") == "stream":
            print("OUTPUT:" + msg["content"]["text"].strip())
    kc.stop_channels()
    print("HOST_ALL_OK")
except Exception as e:
    print(f"HOST_FAIL: {{e}}")
    import traceback; traceback.print_exc()
'''
result = subprocess.run([PYTHON, "-c", host_connect], capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[-300:])

# 9. 清理
print("\n6. Cleanup...")
run("docker rm -f dai-test-v2")
os.remove(CONN_FILE)
os.remove(connect_file)
print("Done")
