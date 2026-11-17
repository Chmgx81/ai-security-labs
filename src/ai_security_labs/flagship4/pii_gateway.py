import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SERVER_PATH = HERE / "pii_server.py"
MAPPING_PATH = HERE / "pii_mapping.json"
LOG_PATH = HERE / "gateway.log"

# Flagship 4, Lesson 2: the model never sees real PII.
# Tool results are tokenized before they cross to the client.
# The mapping table stays here, on the operator's side.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"\+\d{3} \d{3} \d{3} \d{4}")

mapping = {}  # uuid -> real value

if MAPPING_PATH.exists():
    mapping = json.loads(MAPPING_PATH.read_text())

def assign(kind, value):
    for uuid, real in mapping.items():
        if real == value:
            return uuid
    prefix = "contact" if kind == "email" else "phone"
    count = sum(1 for k in mapping if k.startswith(prefix))
    uuid = f"{prefix}-uuid-{count + 1:04d}"
    mapping[uuid] = value
    return uuid

def tokenize(text):
    text = EMAIL_PATTERN.sub(lambda m: assign("email", m.group(0)), text)
    text = PHONE_PATTERN.sub(lambda m: assign("phone", m.group(0)), text)
    return text

def log(entry):
    # NOTE: never log raw PII. A log full of PII is a new leak.
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

server = subprocess.Popen(
    [sys.executable, str(SERVER_PATH)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)

for line in sys.stdin:
    request = json.loads(line)
    server.stdin.write(json.dumps(request) + "\n")
    server.stdin.flush()
    if request.get("id") is not None:
        response = json.loads(server.stdout.readline())
        if request.get("method") == "tools/call":
            before = response["result"]["content"][0]["text"]
            after = tokenize(before)
            if after != before:
                log({
                    "time": str(datetime.now()),
                    "event": "tokenized",
                    "tool": request["params"]["name"],
                    "emails": len(EMAIL_PATTERN.findall(before)),
                    "phones": len(PHONE_PATTERN.findall(before)),
                })
                MAPPING_PATH.write_text(json.dumps(mapping, indent=2))
                response["result"]["content"][0]["text"] = after
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

server.stdin.close()
server.wait()