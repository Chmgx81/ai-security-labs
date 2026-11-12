import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SERVER_PATH = HERE.parent / "flagship1" / "poison_server.py"
LOG_PATH = HERE / "gate.log"

# Flagship 2: the permission gate. No content inspection, no guards.
# This client reads notes. It may never touch the config.
ALLOWED_TOOLS = {"get_current_time", "read_notes"}

server = subprocess.Popen(
    [sys.executable, str(SERVER_PATH)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)

def write_log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

def log(direction, message):
    write_log({"time": str(datetime.now()), "direction": direction, "message": message})

def gate(request):
    """The ONLY defense. Returns None if the call is permitted,
    or a refusal if it is not (the server never sees it)."""
    if request.get("method") != "tools/call":
        return None
    name = request["params"]["name"]
    if name in ALLOWED_TOOLS:
        return None
    log("GATE", f"blocked tools/call: {name} not in allowlist")
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "content": [{"type": "text", "text": f"error: tool '{name}' is not permitted for this client"}],
            "isError": True,
        },
    }

for line in sys.stdin:
    request = json.loads(line)
    refusal = gate(request)
    if refusal is not None:
        log("gate->client", refusal)
        sys.stdout.write(json.dumps(refusal) + "\n")
        sys.stdout.flush()
        continue
    log("client->server", request)
    server.stdin.write(json.dumps(request) + "\n")
    server.stdin.flush()
    if request.get("id") is not None:
        response = json.loads(server.stdout.readline())
        log("server->client", response)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

server.stdin.close()
server.wait()