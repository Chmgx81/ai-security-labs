import base64
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SERVER_PATH = HERE.parent / "flagship1" / "poison_server.py"
LOG_PATH = HERE / "approval.log"

# Flagship 3, Lesson 3: approve must not mean unfiltered.
# rule: allow | deny | approve
POLICY = {
    "get_current_time": {"rule": "allow"},
    "read_notes": {"rule": "allow"},
    "read_config": {
        "rule": "approve",
        "data_class": "internal server configuration, contains credentials",
        "operator_note": "not part of the notes feature",
    },
}

# A DETECTOR stacked under the boundary and the human.
# Job: shrink the blast radius of approvals. Not built to be unbeatable.
SECRET_PATTERNS = [
    re.compile(r"CANARY-\d+"),
    re.compile(r"(?i)(?:db_)?(?:password|passwd|secret|token|api[_-]?key)\s*=\s*\S+"),
]

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

user_request = ""        # what the human asked the agent to do
tool_descriptions = {}   # name -> description, UNTRUSTED (the server wrote them)

def scrub(text):
    """Decode if encoded, then scrub credential-shaped content."""
    candidate = text.strip()
    try:
        candidate = base64.b64decode(candidate, validate=True).decode("utf-8")
        log("GATE", "result was base64-encoded: decoded before scrubbing")
    except Exception:
        pass
    for pat in SECRET_PATTERNS:
        candidate = pat.sub("[REDACTED]", candidate)
    return candidate

def ask_human(name, args):
    """The approval channel: the real terminal, not the model's pipe."""
    lines = [
        "",
        "[APPROVAL] -----------------------------",
        f"[APPROVAL] you asked:        {user_request!r}",
        f"[APPROVAL] the agent calls: {name}({args})",
        f"[APPROVAL] operator label:  {POLICY[name].get('data_class', 'unknown')}",
        f"[APPROVAL] operator note:   {POLICY[name].get('operator_note', '')}",
        "[APPROVAL] tool says (UNTRUSTED, written by the server):",
        f"[APPROVAL]   {tool_descriptions.get(name, '(no description)')[:100]}",
        "[APPROVAL] approve? [y/N] ",
    ]
    with open("/dev/tty", "w") as out:
        out.write("\n".join(lines))
        out.flush()
    with open("/dev/tty") as inp:
        answer = inp.readline().strip().lower()
    approved = answer == "y"
    log("HUMAN", f"approval for {name}: {'granted' if approved else 'refused'}")
    return approved

def decide(request):
    """Returns None to forward, or a refusal result to block."""
    method = request.get("method")
    if method == "initialize":
        global user_request
        user_request = (request["params"].get("clientInfo", {}) or {}).get("context", "")
        return None
    if method != "tools/call":
        return None
    name = request["params"]["name"]
    rule = POLICY.get(name, {}).get("rule", "deny")
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
        if request.get("method") == "tools/list":
            for t in response["result"]["tools"]:
                tool_descriptions[t["name"]] = t["description"]
        if request.get("method") == "tools/call":
            before = response["result"]["content"][0]["text"]
            after = scrub(before)
            if after != before:
                log("GATE", "redacted approved tool result before the model saw it")
            response["result"]["content"][0]["text"] = after
        log("server->client", response)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

server.stdin.close()
server.wait()