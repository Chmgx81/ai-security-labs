import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SERVER_PATH = HERE / "poison_server.py"
LOG_PATH = HERE / "proxy.log"

CANARY = "CANARY-8842"
POISON_MARKERS = ["IMPORTANT SYSTEM", "you MUST", "Do not mention"]

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

def guard(response):
    """Enforce proxy policy on every response crossing the wire."""
    result = response.get("result", {})

    # Guard 1: no imperative instructions in descriptions reaching the model
    for tool in result.get("tools", []):
        description = tool["description"]
        lowered = description.lower()
        for marker in POISON_MARKERS:
            if marker.lower() in lowered:
                cut = lowered.find(marker.lower())
                tool["description"] = description[:cut].strip() + " [description sanitized by proxy]"
                log("GUARD", f"stripped imperative language from description of: {tool['name']}")
                break

    # Guard 2: the canary never crosses toward the user or the model
    for content in result.get("content", []):
        if CANARY in content.get("text", ""):
            content["text"] = content["text"].replace(CANARY, "[blocked by proxy]")
            log("GUARD", "redacted canary from a tool result")

    return response

for line in sys.stdin:
    request = json.loads(line)
    log("client->server", request)
    server.stdin.write(json.dumps(request) + "\n")
    server.stdin.flush()

    if request.get("id") is not None:
        response = json.loads(server.stdout.readline())
        response = guard(response)
        log("server->client", response)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

server.stdin.close()
server.wait()