import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PROXY_PATH = HERE / "approval_proxy.py"

# Headless: the proxy runs in a new session with NO controlling terminal,
# so the approval channel cannot find a human. The approve rule must
# refuse (fail closed), not hang, not auto-approve.
proxy = subprocess.Popen(
    [sys.executable, str(PROXY_PATH)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    start_new_session=True,
)

def send(obj):
    proxy.stdin.write(json.dumps(obj) + "\n")
    proxy.stdin.flush()

def receive():
    return json.loads(proxy.stdout.readline())

results = []

def check(name, condition, detail=""):
    results.append((name, condition))
    line = "PASS" if condition else "FAIL"
    line += f": {name}"
    if not condition and detail:
        line += f" ({detail})"
    print(line)

# 1. Handshake
send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "approval-test", "version": "0.1", "context": "Read my notes."}}})
init = receive()
check("initialize passes through", init["result"]["serverInfo"]["name"] == "poison-mini")
send({"jsonrpc": "2.0", "method": "notifications/initialized"})

# 2. tools/list: all three tools visible (flagship 3 shows, then gates)
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
names = [t["name"] for t in receive()["result"]["tools"]]
check("all tools visible in tools/list", set(names) == {"get_current_time", "read_notes", "read_config"}, f"got {names}")

# 3. allow rule: read_notes works
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_notes", "arguments": {}}})
res = receive()
check("read_notes passes through", not res["result"].get("isError", False))

# 4. default-deny: tools missing from the policy are refused
send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "read_everything", "arguments": {}}})
res = receive()
text = res["result"]["content"][0]["text"]
check("unknown tool refused (default deny)", res["result"].get("isError") is True and text == "error: tool call failed", f"got {text!r}")

# 5. approve rule with no human: must fail closed, immediately
send({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "read_config", "arguments": {}}})
res = receive()
text = res["result"]["content"][0]["text"]
check("read_config fails closed when headless", res["result"].get("isError") is True and text == "error: tool call failed", f"got {text!r}")

proxy.stdin.close()
proxy.wait()

fails = [n for n, ok in results if not ok]
print()
print(f"{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("REGRESSION: the approval gate failed:")
    for n in fails:
        print(f"  - {n}")
    sys.exit(1)
print("approval gate regression test: all clear")