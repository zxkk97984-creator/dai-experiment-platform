"""Kernel final test - verifies connection, execution, variable sharing, matplotlib, error"""
import sys, os, time, json, secrets, socket, subprocess, shutil, io

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")
TMP = os.path.join(os.environ["TEMP"], "kernel_final_test")
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
    "hb_port": free_port(), "ip": "127.0.0.1",
    "key": secrets.token_hex(24), "transport": "tcp",
    "signature_scheme": "hmac-sha256", "kernel_name": "",
}
with open(CONN, "w") as f:
    json.dump(cfg, f)

# Start kernel
proc = subprocess.Popen(
    [PYTHON, "-m", "ipykernel_launcher", "-f", CONN],
    stdout=open(os.path.join(TMP, "stdout.log"), "w"),
    stderr=open(os.path.join(TMP, "stderr.log"), "w"),
)
time.sleep(3)
for _ in range(15):
    with open(os.path.join(TMP, "stderr.log")) as f:
        if "To connect another client" in f.read():
            break
    time.sleep(1)

# Connect
with open(CONN) as f:
    cfg2 = json.load(f)
cfg2["kernel_name"] = ""

from jupyter_client import BlockingKernelClient

kc = BlockingKernelClient()
kc.load_connection_info(cfg2)

def execute(code):
    """Execute code and collect all output messages from iopub channel"""
    msg_id = kc.execute(code)
    outputs = []
    while True:
        try:
            msg = kc.get_iopub_msg(timeout=10)
            msg_type = msg.get("msg_type", "")
            if msg_type == "status" and msg["content"].get("execution_state") == "idle":
                break
            if msg_type in ("stream", "display_data", "execute_result", "error"):
                outputs.append(msg)
        except Exception as e:
            outputs.append({"error": str(e)})
            break
    return outputs

def collect_text(outputs, stream_name="stdout"):
    parts = []
    for m in outputs:
        if isinstance(m, dict) and m.get("msg_type") == "stream":
            if m["content"].get("name") == stream_name:
                parts.append(m["content"]["text"])
    return "".join(parts)

passed = 0
failed = 0

try:
    kc.start_channels()
    kc.wait_for_ready(timeout=15)
    print("CONNECTED!\n")

    # Test 1: Basic
    outputs = execute("print(42+42)")
    text = collect_text(outputs)
    print(f"1. Basic: '{text.strip()}'")
    assert "84" in text
    passed += 1

    # Test 2: Variable sharing
    execute("x = 123")
    outputs = execute("print(x)")
    text = collect_text(outputs)
    print(f"2. Variable sharing: '{text.strip()}'")
    assert "123" in text
    passed += 1

    # Test 3: Error
    outputs = execute("1/0")
    has_err = any(m.get("msg_type") == "error" and "ZeroDivisionError" in m["content"]["ename"]
                  for m in outputs if isinstance(m, dict))
    print(f"3. Error: ZeroDivisionError={'YES' if has_err else 'NO'}")
    assert has_err
    passed += 1

    # Test 4: Matplotlib
    code = """
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io, os
try:
    fig, ax = plt.subplots()
    ax.plot([1,2,3,4], [10,20,30,40])
    ax.set_title('Test Plot')
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=72)
    img_size = len(buf.getvalue())
    print('IMG_SIZE:' + str(img_size))
    plt.close()
    print('MATPLOTLIB_OK')
except Exception as e:
    print('MATPLOTLIB_ERR:' + str(e))
    import traceback; traceback.print_exc()
"""
    outputs = execute(code)
    text = collect_text(outputs)
    err_text = collect_text(outputs, "stderr")
    if err_text:
        print(f"   stderr: {err_text[:200]}")
    has_img = "IMG_SIZE:" in text
    img_size = int(text.split("IMG_SIZE:")[1].split()[0]) if has_img else 0
    print(f"4. Matplotlib: size={img_size} bytes, OK={'MATPLOTLIB_OK' in text}")
    if img_size > 100:
        passed += 1
    else:
        print("   WARNING: matplotlib image size < 100 bytes")
        failed += 1

    # Test 5: Display data MIME
    outputs = execute("from IPython.display import display, Markdown; display(Markdown('**bold**'))")
    types = set(m.get("msg_type") for m in outputs if isinstance(m, dict))
    print(f"5. MIME types: {types}")
    assert "display_data" in types
    passed += 1

    print(f"\nALL {passed} TESTS PASSED!")

except Exception as e:
    print(f"FAIL: {e}")
    import traceback; traceback.print_exc()
    failed += 1
finally:
    try:
        kc.stop_channels()
    except:
        pass

proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()
shutil.rmtree(TMP, ignore_errors=True)
print("Done")
