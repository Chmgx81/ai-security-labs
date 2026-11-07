import requests

response = requests.post(
    "http://localhost:11434/api/chat",

    json={
        "model": "qwen3.5:4b",
        "messages": [
            {"role": "user", "content": "Say exactly: hello from my own GPU"}
        ],
        "stream": False,
    }
)

print(response.status_code)
print(response.json()["message"]["content"])