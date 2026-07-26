"""诊断 Docker kernel 创建失败原因"""
import json, secrets, socket, subprocess, time, os

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p

ports = [free_port() for _ in range(5)]
conn = {
    "shell_port": ports[0], "iopub_port": ports[1], "stdin_port": ports[2],
    "control_port": ports[3], "hb_port": ports[4],
    "ip": "0.0.0.0", "key": secrets.token_hex(24),
    "transport": "tcp", "signature_scheme": "hmac-sha256", "kernel_name": "",
}

tmpdir = os.path.join(os.environ["TEMP"], "dai-kernels")
os.makedirs(tmpdir, exist_ok=True)
conn_path = os.path.join(tmpdir, "kernel-rec-2.json")
with open(conn_path, "w") as f:
    json.dump(conn, f)
print(f"Ports: {ports}")

# Clean old container
subprocess.run(["docker", "rm", "-f", "dai-kernel-rec-2"], capture_output=True)

# Build command
conn_str = json.dumps(conn)
cmd = [
    "docker", "run", "-d", "--name", "dai-kernel-rec-2",
    "--cpus", "1", "--memory", "512m", "--pids-limit", "50",
    "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",
    "-l", "dai.record_id=2",
]
for p in ports:
    cmd.extend(["-p", f"127.0.0.1:{p}:{p}"])
cmd.extend([
    "dai-kernel-python:latest",
    "bash", "-c",
    f"""python3 -c 'import json; json.dump({conn_str}, open("/tmp/conn.json","w"))' && exec python -m ipykernel_launcher -f /tmp/conn.json""",
])

print(f"Running container...")
result = subprocess.run(cmd, capture_output=True, text=True)
print(f"stdout: {result.stdout.strip()}")
print(f"stderr: {result.stderr.strip()[:500]}")
print(f"Return code: {result.returncode}")

if result.returncode == 0:
    time.sleep(5)
    alive = subprocess.run(["docker", "ps", "-q", "-f", "name=dai-kernel-rec-2"], capture_output=True, text=True)
    print(f"Container alive: {bool(alive.stdout.strip())}")

    if alive.stdout.strip():
        logs = subprocess.run(["docker", "logs", "dai-kernel-rec-2"], capture_output=True, text=True)
        print(f"Logs:\n{logs.stdout[-500:]}")
        if logs.stderr:
            print(f"Stderr:\n{logs.stderr[-500:]}")
    else:
        # Container died - get logs
        logs = subprocess.run(["docker", "logs", "dai-kernel-rec-2"], capture_output=True, text=True)
        print(f"Dead container logs:\n{logs.stdout[-1000:]}")
        print(f"Dead container stderr:\n{logs.stderr[-1000:]}")
        subprocess.run(["docker", "rm", "-f", "dai-kernel-rec-2"], capture_output=True)
