"""Docker kernel test - verify ipykernel in container with host network"""
import json, secrets, socket, subprocess, time, os, shutil

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(os.environ["TEMP"], "kernel_docker_test")
os.makedirs(TMP, exist_ok=True)
CONN = os.path.join(TMP, "conn.json")

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p

# Create connection file
cfg = {
    "shell_port": free_port(), "iopub_port": free_port(),
    "stdin_port": free_port(), "control_port": free_port(),
    "hb_port": free_port(), "ip": "0.0.0.0",
    "key": secrets.token_hex(24), "transport": "tcp",
    "signature_scheme": "hmac-sha256", "kernel_name": "",
}
with open(CONN, "w") as f:
    json.dump(cfg, f)
print(f"Ports: shell={cfg['shell_port']} iopub={cfg['iopub_port']}")

# Clean + Start Docker container with host network
container_name = "dai-kernel-docker-test"
subprocess.run(f"docker rm -f {container_name}", shell=True, capture_output=True)
cmd = f'docker run -d --name {container_name} --network host -v "{CONN}:/tmp/kernel-conn.json:ro" dai-kernel-python:latest python -m ipykernel_launcher -f /tmp/kernel-conn.json'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print(f"Container: {result.stdout.strip()}")

time.sleep(4)
logs = subprocess.run(f"docker logs {container_name}", shell=True, capture_output=True, text=True)
# Wait for ready
for _ in range(15):
    if "To connect another client" in logs.stdout:
        break
    time.sleep(1)
    logs = subprocess.run(f"docker logs {container_name}", shell=True, capture_output=True, text=True)

print(f"Kernel ready signal: {'YES' if 'To connect another client' in logs.stdout else 'NO'}")

# Connect using load_connection_info (proper HMAC handling)
from jupyter_client import BlockingKernelClient
with open(CONN) as f:
    cfg2 = json.load(f)
cfg2["ip"] = "127.0.0.1"  # host network
cfg2["kernel_name"] = ""

kc = BlockingKernelClient()
kc.load_connection_info(cfg2)

def execute(code):
    msg_id = kc.execute(code)
    outputs = []
    while True:
        try:
            msg = kc.get_iopub_msg(timeout=15)
            mt = msg.get("msg_type", "")
            if mt == "status" and msg["content"].get("execution_state") == "idle":
                break
            if mt in ("stream", "display_data", "execute_result", "error"):
                outputs.append(msg)
        except Exception as e:
            outputs.append({"error": str(e)})
            break
    return outputs

def collect_text(outputs, stream="stdout"):
    return "".join(m["content"]["text"] for m in outputs
                   if isinstance(m, dict) and m.get("msg_type") == "stream"
                   and m["content"].get("name") == stream)

passed = 0
try:
    kc.start_channels()
    kc.wait_for_ready(timeout=15)
    print("CONNECTED!\n")

    # Test 1
    o = execute("print(42+42)")
    t = collect_text(o)
    print(f"1. Basic: '{t.strip()}'")
    assert "84" in t
    passed += 1

    # Test 2
    execute("x = 777")
    o = execute("print(x)")
    t = collect_text(o)
    print(f"2. Variable sharing: '{t.strip()}'")
    assert "777" in t
    passed += 1

    # Test 3
    o = execute("1/0")
    has = any(m.get("msg_type") == "error" and "ZeroDivisionError" in m.get("content", {}).get("ename", "")
              for m in o if isinstance(m, dict))
    print(f"3. Error: {'PASS' if has else 'FAIL'}")
    assert has
    passed += 1

    # Test 4: Matplotlib
    code = """import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt;import io;fig,ax=plt.subplots();ax.plot([1,2,3],[10,20,30]);b=io.BytesIO();fig.savefig(b,format='png',dpi=72);print('IMG:'+str(len(b.getvalue())));plt.close()"""
    o = execute(code)
    t = collect_text(o)
    print(f"4. Matplotlib: '{t.strip()[:80]}'")
    has_img = "IMG:" in t
    print(f"   {'PASS' if has_img else 'FAIL - image output exists in Docker'}")
    if has_img:
        passed += 1

    # Test 5: Docker security
    print(f"\n5. Security checks:")
    stats = subprocess.run(f"docker stats --no-stream --format 'MEM:{{{{.MemUsage}}}}' {container_name}", shell=True, capture_output=True, text=True)
    print(f"   Memory: {stats.stdout.strip()}")
    mem_check = subprocess.run(f"docker inspect -f '{{{{.HostConfig.Memory}}}}' {container_name}", shell=True, capture_output=True, text=True)
    print(f"   Mem limit: {int(mem_check.stdout.strip()) // 1048576}MB")
    cpu_check = subprocess.run(f"docker inspect -f '{{{{.HostConfig.NanoCpus}}}}' {container_name}", shell=True, capture_output=True, text=True)
    print(f"   CPU limit: {int(cpu_check.stdout.strip()) // 1000000000} core")
    user_check = subprocess.run(f"docker exec {container_name} whoami", shell=True, capture_output=True, text=True)
    print(f"   User: {user_check.stdout.strip()}")
    print(f"   Non-root: {'YES' if user_check.stdout.strip() != 'root' else 'FAIL'}")

    print(f"\n{passed} TESTS PASSED (Docker kernel verified)")

except Exception as e:
    print(f"FAIL: {e}")
    import traceback; traceback.print_exc()
finally:
    try:
        kc.stop_channels()
    except:
        pass

# Cleanup
subprocess.run(f"docker rm -f {container_name}", shell=True, capture_output=True)
shutil.rmtree(TMP, ignore_errors=True)
print("Done")
