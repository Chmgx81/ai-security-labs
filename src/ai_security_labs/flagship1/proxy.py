import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SERVER_PATH = HERE / "poison_server.py"
LOG_PATH = HERE / "proxy.log"

server = subprocess.Popen(
    [sys.executable, str(SERVER_PATH)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)

def log(direction, message):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"time": str(datetime.now()), "direction": direction, "message": message}) + "\n")

for line in sys.stdin:
    request = json.loads(line)
    log("client->server", request)
    server.stdin.write(json.dumps(request) + "\n")
    server.stdin.flush()

    # a request with an id expects exactly one response; a notification expects none
    if request.get("id") is not None:
        response = json.loads(server.stdout.readline())
        log("server->client", response)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

server.stdin.close()
server.wait()