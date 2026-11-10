import json
import sys
from datetime import datetime

TOOLS = [
    {
        "name": "get_current_time",
        "description": "Get the current date and time on this machine.",
        "inputSchema": {"type": "object", "properties": {}},
    }
]

def reply(id_, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": id_, "result": result}) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    id_ = message.get("id")
    if method == "initialize":
        reply(id_, {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "mini", "version": "0.1"},
        })
    elif method == "tools/list":
        reply(id_, {"tools": TOOLS})
    elif method == "tools/call":
        reply(id_, {
            "content": [{"type": "text", "text": f"Current time: {datetime.now()}"}],
            "isError": False,
        })