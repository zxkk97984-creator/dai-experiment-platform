"""Kernel v2 - 纯ASCII代码测试"""
import json, secrets, socket, subprocess, time, os

WIN_TEMP = os.environ.get("TEMP", "/tmp")
CONN_FILE = os.path.join(WIN_TEMP, "kernel-v2.json")
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

# Clean
run("docker rm -f dai-kv2")

# Create conn file
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
print(f"File: {CONN_FILE}, ports: {cfg['shell_port']} {cfg['iopub_port']} {cfg['stdin_port']} {cfg['control_port']} {cfg['hb_port']}")

# Start container with host network
run(f'docker run -d --name dai-kv2 --network host -v "{CONN_FILE}:/tmp/kernel-conn.json:ro" dai-kernel-python:latest python -m ipykernel_launcher -f /tmp/kernel-conn.json')
time.sleep(4)

# Check
status = run("docker ps --filter name=dai-kv2 --format '{{.Status}}'")
print(f"Status: {status.stdout.strip()}")

# Internal connection via docker exec (pure ASCII code)
connect_py = r"""
import json
with open("/tmp/kernel-conn.json") as f:
    cfg = json.load(f)
cfg["ip"] = "127.0.0.1"
cfg["kernel_name"] = ""
from jupyter_client import BlockingKernelClient
kc = BlockingKernelClient(**{k:v for k,v in cfg.items()
    if k in ("shell_port","iopub_port","stdin_port","hb_port","control_port","ip","key","transport","signature_scheme","kernel_name")})
kc.start_channels()
kc.wait_for_ready(timeout=10)
print("CONNECTED")
# Cell 1
reply = kc.execute_interactive("x = 10")
# Cell 2
reply2 = kc.execute_interactive("print(x * 2)")
for msg in reply2:
    if msg.get("msg_type") == "stream":
        print("CELL2_OUTPUT:", msg["content"]["text"].strip())
kc.stop_channels()
print("INTERNAL_OK")
"""
connect_file = os.path.join(WIN_TEMP, "kv2_connect.py")
with open(connect_file, "w", encoding="ascii") as f:
    f.write(connect_py)

run(f"docker cp {connect_file} dai-kv2:/tmp/connect.py")
result = run("docker exec dai-kv2 python3 /tmp/connect.py")
print("INTERNAL:", result.stdout)
if result.stderr:
    print("ERR:", result.stderr[:200])

# Host connection
print("\n--- Host connection ---")
host_py = f"""
import json
with open(r"{CONN_FILE}") as f:
    cfg = json.load(f)
cfg["ip"] = "127.0.0.1"
cfg["kernel_name"] = ""
from jupyter_client import BlockingKernelClient
kc = BlockingKernelClient(**{{k:v for k,v in cfg.items()
    if k in ("shell_port","iopub_port","stdin_port","hb_port","control_port","ip","key","transport","signature_scheme","kernel_name")}})
kc.start_channels()
kc.wait_for_ready(timeout=10)
print("HOST_CONNECTED")
reply = kc.execute_interactive("print('host_hello')")
for msg in reply:
    if msg.get("msg_type") == "stream":
        print("HOST_OUTPUT:", msg["content"]["text"].strip())
kc.stop_channels()
print("HOST_OK")
"""
result = subprocess.run([os.path.join(BACKEND, ".venv", "Scripts", "python.exe"), "-c", host_py], capture_output=True, text=True)
print("HOST:", result.stdout)
if result.stderr:
    print("HOST_ERR:", result.stderr[-300:])

# Cleanup
run("docker rm -f dai-kv2")
os.remove(CONN_FILE)
os.remove(connect_file)
print("\nDone")
