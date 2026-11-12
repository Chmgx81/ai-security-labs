import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
GATE_PATH = HERE / "gate_proxy.py"

gate = subprocess.Popen(
    [sys.executable, str(GATE_PATH)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)

def send(obj):
    gate.stdin.write(json.dumps(obj) + "\n")
    gate.stdin.flush()

def receive():
    return json.loads(gate.stdout.readline())

results = []

def check(name, condition, detail=""):
    results.append((name, condition))
    line = "PASS" if condition else "FAIL"
    line += f": {name}"
    if not condition and detail:
        line += f" ({detail})"
    print(line)

# --- 1. Handshake passes through untouched ---
send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "gate-test", "version": "0.1"}}})
init = receive()
check("initialize passes through", init["result"]["serverInfo"]["name"] == "poison-mini")
send({"jsonrpc": "2.0", "method": "notifications/initialized"})

# --- 2. Layer 1: unauthorized tools are invisible ---
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
names = [t["name"] for t in receive()["result"]["tools"]]
check("read_config invisible in tools/list", set(names) == {"get_current_time", "read_notes"}, f"got {names}")

# --- 3. Allowed call passes through and works ---
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_notes", "arguments": {}}})
res = receive()
check("read_notes passes through", not res["result"].get("isError", False))

# --- 4. Layer 2: hallucinated/hidden call is blocked anyway ---
# Run 3 of Lesson 2: the model called read_config without ever seeing it.
# The gate must refuse it no matter where the idea came from.
send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "read_config", "arguments": {}}})
res = receive()
text = res["result"]["content"][0]["text"]
check("read_config refused", res["result"].get("isError") is True, f"got {text[:60]!r}")
check("refusal is bare (no tool name leaked)", text == "error: tool call failed", f"got {text!r}")

# --- 5. The secret must not cross, in any form ---
# If the gate ever forwards read_config, the response becomes the base64
# config blob and this exact-text check fails. Output, not logs.
check("no config content crossed", "internal server configuration" not in text and "error" in text)

# --- 6. Repeated attempts get the same refusal, no escalation path ---
send({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "read_config", "arguments": {}}})
res = receive()
check("second attempt also refused", res["result"].get("isError") is True)

gate.stdin.close()
gate.wait()

fails = [n for n, ok in results if not ok]
print()
print(f"{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("REGRESSION: the gate failed:")
    for n in fails:
        print(f"  - {n}")
    sys.exit(1)
print("gate regression test: all clear")