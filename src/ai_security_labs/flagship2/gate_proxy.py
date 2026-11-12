import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SERVER_PATH = HERE.parent / "flagship1" / "poison_server.py"
LOG_PATH = HERE / "gate.log"

# Flagship 2, Lesson 2: deny by invisibility + bare refusals.
# The MODEL sees: only allowed tools, bare "error: tool call failed".
# The OPERATOR sees: everything, in gate.log.
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
    """Allowlist on the tool call. None = forward, refusal = block."""
    if request.get("method") != "tools/call":
        return None
    name = request["params"]["name"]
    if name in ALLOWED_TOOLS:
        return None
    # Operator gets the full story. The model gets nothing useful.
    log("GATE", f"blocked tools/call: {name} not in allowlist")
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "content": [{"type": "text", "text": "error: tool call failed"}],
            "isError": True,
        },
    }

def visible(response):
    """Filter tools/list: unauthorized tools are invisible to the model."""
    tools = (response.get("result") or {}).get("tools")
    if tools is None:
        return response
    hidden = [t["name"] for t in tools if t["name"] not in ALLOWED_TOOLS]
    if hidden:
        log("GATE", f"hid from tools/list: {', '.join(hidden)}")
        response["result"]["tools"] = [t for t in tools if t["name"] in ALLOWED_TOOLS]
    return response

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
        if request.get("method") == "tools/list":
            response = visible(response)
        log("server->client", response)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

server.stdin.close()
server.wait()