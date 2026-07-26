"""诊断：模拟 kernel_manager.execute 的完整流程"""
import json, time, socket, subprocess, os

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p

# 1. 生成连接文件 (模拟 _generate_conn_info)
import secrets
from jupyter_client import write_connection_file

conn_dir = os.path.join(os.environ["TEMP"], "dai-kernels")
os.makedirs(conn_dir, exist_ok=True)
conn_path = os.path.join(conn_dir, "diag.json")
key = secrets.token_hex(24).encode("ascii")
write_connection_file(conn_path, ip="0.0.0.0", key=key)

with open(conn_path) as f:
    conn_info = json.load(f)

# 强制确保 IP
if conn_info["ip"] != "0.0.0.0":
    conn_info["ip"] = "0.0.0.0"
    with open(conn_path, "w") as f:
        json.dump(conn_info, f)

ports = [conn_info[k] for k in ("shell_port","iopub_port","stdin_port","control_port","hb_port")]
print(f"1. Ports: {ports}, IP in file: {conn_info['ip']}")

# 2. 启动容器 (模拟 create_session)
subprocess.run(["docker", "rm", "-f", "dai-diag"], capture_output=True)
cmd = ["docker", "run", "-d", "--name", "dai-diag", "--cpus", "1", "--memory", "512m", "--pids-limit", "50"]
for p in ports:
    cmd.extend(["-p", f"127.0.0.1:{p}:{p}"])
cmd.extend(["-v", f"{conn_path}:/tmp/conn.json:ro"])
cmd.extend(["dai-kernel-python:latest", "python", "-m", "ipykernel_launcher", "-f", "/tmp/conn.json"])
r = subprocess.run(cmd, capture_output=True, text=True)
print(f"2. Container start: rc={r.returncode} id={r.stdout.strip()[:12]}")
time.sleep(5)

# 3. 连接并执行 (模拟 execute 方法)
conn_info["ip"] = "127.0.0.1"
conn_info["kernel_name"] = ""
print(f"3. Connecting to 127.0.0.1, ports: {ports[0]}-{ports[4]}")

from jupyter_client import BlockingKernelClient
kc = BlockingKernelClient()
kc.load_connection_info(conn_info)
kc.start_channels()

# 检查是否就绪
kc.wait_for_ready(timeout=10)
print("   Kernel ready!")

# 执行代码
print("4. Executing print(42+42)...")
start = time.perf_counter()
kc.execute("print(42+42)")

outputs = []
try:
    while True:
        msg = kc.get_iopub_msg(timeout=15)
        mt = msg.get("msg_type", "")
        print(f"   Got msg: {mt}")
        if mt == "status":
            es = msg["content"].get("execution_state", "")
            print(f"   -> exec_state: {es}")
            if es == "idle":
                break
        elif mt in ("stream", "display_data", "execute_result", "error"):
            content = dict(msg["content"])
            if "data" in content:
                content["data"] = {
                    k: (v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v)
                    for k, v in content["data"].items()
                }
            outputs.append({"msg_type": mt, "content": content})
            if mt == "stream":
                print(f"   -> STREAM: '{content['text'].strip()}'")
except Exception as e:
    print(f"   Exception: {type(e).__name__}: {e}")

elapsed = int((time.perf_counter() - start) * 1000)
kc.stop_channels()
print(f"5. Result: {len(outputs)} outputs in {elapsed}ms")

subprocess.run(["docker", "rm", "-f", "dai-diag"], capture_output=True)
print("Done")
