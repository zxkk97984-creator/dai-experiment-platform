"""Local kernel test - no Docker, verify jupyter_client + ipykernel basic mechanism"""
import json, secrets, socket, subprocess, time, os, sys, signal

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")
TMPDIR = os.path.join(os.environ.get("TEMP", "/tmp"), "kernel_local_test")
os.makedirs(TMPDIR, exist_ok=True)

def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]

CONN_FILE = os.path.join(TMPDIR, "kernel.json")

# 1. Create connection file
cfg = {
    "shell_port": free_port(),
    "iopub_port": free_port(),
    "stdin_port": free_port(),
    "control_port": free_port(),
    "hb_port": free_port(),
    "ip": "127.0.0.1",
    "key": secrets.token_hex(24),
    "transport": "tcp",
    "signature_scheme": "hmac-sha256",
    "kernel_name": "",
}
with open(CONN_FILE, "w") as f:
    json.dump(cfg, f)
print(f"1. Connection file: {CONN_FILE}")
print(f"   Ports: shell={cfg['shell_port']}")

# 2. Start kernel
print("\n2. Starting local kernel...")
kernel_proc = subprocess.Popen(
    [PYTHON, "-m", "ipykernel_launcher", "-f", CONN_FILE],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
time.sleep(3)
if kernel_proc.poll() is not None:
    out, err = kernel_proc.communicate()
    print(f"   ERROR: Kernel died immediately!")
    print(f"   stdout: {out.decode()[:500]}")
    print(f"   stderr: {err.decode()[:500]}")
    sys.exit(1)
print(f"   Kernel PID: {kernel_proc.pid}")

# 3. Connect
print("\n3. Connecting...")
with open(CONN_FILE) as f:
    cfg2 = json.load(f)
cfg2["kernel_name"] = ""
from jupyter_client import BlockingKernelClient

kc = BlockingKernelClient(**{k: v for k, v in cfg2.items()
    if k in ("shell_port", "iopub_port", "stdin_port", "hb_port", "control_port",
             "ip", "key", "transport", "signature_scheme", "kernel_name")})

try:
    kc.start_channels()
    kc.wait_for_ready(timeout=10)
    print("   Connected!")

    # Test 1: Basic execution
    print("\n4. Tests:")
    print("   a) Basic print...", end=" ")
    reply = kc.execute_interactive("print(42+42)")
    text = ""
    for msg in reply:
        if msg.get("msg_type") == "stream":
            text += msg["content"]["text"]
    assert "84" in text, f"Expected 84, got: {text}"
    print("OK")

    # Test 2: Variable sharing
    print("   b) Variable sharing...", end=" ")
    kc.execute_interactive("x = 999")
    reply = kc.execute_interactive("print(x)")
    text = ""
    for msg in reply:
        if msg.get("msg_type") == "stream":
            text += msg["content"]["text"]
    assert "999" in text, f"Expected 999, got: {text}"
    print("OK")

    # Test 3: Matplotlib
    print("   c) Matplotlib...", end=" ")
    code = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
fig, ax = plt.subplots()
ax.plot([1,2,3,4], [10,20,30,40])
buf = io.BytesIO()
fig.savefig(buf, format='png', dpi=72)
print('IMG_SIZE:' + str(len(buf.getvalue())))
plt.close()
"""
    reply = kc.execute_interactive(code)
    text = ""
    for msg in reply:
        if msg.get("msg_type") == "stream":
            text += msg["content"]["text"]
    assert "IMG_SIZE:" in text, f"Expected IMG_SIZE, got: {text[:100]}"
    size = int(text.split("IMG_SIZE:")[1].strip())
    print(f"OK (image size: {size} bytes)")

    # Test 4: Error traceback
    print("   d) Error traceback...", end=" ")
    reply = kc.execute_interactive("1/0")
    has_error = False
    for msg in reply:
        if msg.get("msg_type") == "error":
            has_error = True
            assert msg["content"]["ename"] == "ZeroDivisionError"
    assert has_error, "No error message received"
    print("OK")

    # Test 5: Multiple outputs (stream + display_data)
    print("   e) Rich MIME output...", end=" ")
    code2 = """
from IPython.display import display, Markdown
print("text output")
display(Markdown("**bold markdown**"))
"""
    reply = kc.execute_interactive(code2)
    types = set()
    for msg in reply:
        types.add(msg.get("msg_type"))
    assert "stream" in types, "No stream output"
    assert "display_data" in types, "No display_data output"
    print(f"OK (output types: {types})")

    print("\n5. All tests passed!")

except Exception as e:
    print(f"\n   FAIL: {e}")
    import traceback; traceback.print_exc()
finally:
    kc.stop_channels()

# 4. Cleanup
print("\n6. Cleanup...")
kernel_proc.terminate()
try:
    kernel_proc.wait(timeout=5)
except:
    kernel_proc.kill()
os.remove(CONN_FILE)
os.rmdir(TMPDIR)
print("Done")
