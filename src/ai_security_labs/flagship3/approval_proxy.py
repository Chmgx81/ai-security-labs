import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SERVER_PATH = HERE.parent / "flagship1" / "poison_server.py"
LOG_PATH = HERE / "approval.log"

# Flagship 3: per-tool policy with human approval.
# allow   -> forward without asking
# deny    -> refuse, bare error to the model
# approve -> pause, ask the human, forward only on a yes
POLICY = {
    "get_current_time": "allow",
    "read_notes": "allow",
    "read_config": "approve",
}

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

def ask_human(name, args):
    """The approval channel: the real terminal, not the model's pipe."""
    with open("/dev/tty", "w") as out:
        out.write(f"\n[APPROVAL] the agent requests: {name}({args})\n[APPROVAL] approve? [y/N] ")
        out.flush()
    with open("/dev/tty") as inp:
        answer = inp.readline().strip().lower()
    approved = answer == "y"
    log("HUMAN", f"approval for {name}: {'granted' if approved else 'refused'}")
    return approved

def decide(request):
    """Returns None to forward, or a refusal result to block."""
    if request.get("method") != "tools/call":
        return None
    name = request["params"]["name"]
    rule = POLICY.get(name, "deny")
    if rule == "allow":
        return None
    if rule == "approve" and ask_human(name, request["params"].get("arguments", {})):
        log("GATE", f"approved tools/call: {name} forwarded after human consent")
        return None
    log("GATE", f"refused tools/call: {name} (rule: {rule})")
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "content": [{"type": "text", "text": "error: tool call failed"}],
            "isError": True,
        },
    }

for line in sys.stdin:
    request = json.loads(line)
    refusal = decide(request)
    if refusal is not None:
        log("proxy->client", refusal)
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