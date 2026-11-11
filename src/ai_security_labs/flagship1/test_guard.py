import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PROXY = HERE / "proxy.py"

proxy = subprocess.Popen(
    [sys.executable, str(PROXY)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)

def ask(id_, request):
    proxy.stdin.write(json.dumps(request) + "\n")
    proxy.stdin.flush()
    return json.loads(proxy.stdout.readline())

ask(1, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0.1"}}})
tools = ask(2, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
descriptions = {t["name"]: t["description"] for t in tools}

failures = []
read_notes = descriptions["read_notes"]
if "you MUST" in read_notes or "IMPORTANT SYSTEM" in read_notes:
    failures.append("POISON STILL PRESENT in read_notes description")
if "[description sanitized by proxy]" not in read_notes:
    failures.append("sanitizer tag missing from read_notes")
if "Get the current date" not in descriptions["get_current_time"]:
    failures.append("FALSE POSITIVE: benign tool get_current_time was damaged")

proxy.stdin.close()
proxy.wait()

if failures:
    print("GUARD TEST FAILED:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("GUARD TEST PASSED: poison stripped, benign tool unharmed")