# What it is 

A tool-poisoning attack and defense lab, built from raw JSON-RPC with no MCP SDK. A poison server hides instructions in a tool description; a local model agent gets tricked; a proxy guards both directions.

### Architecture


`client (mini_client.py + Ollama qwen3.5:4b)
   ↕ stdio, JSON-RPC
proxy (proxy.py)  — guard 1: sanitizes tool descriptions (server→client)
   ↕              guard 2: redacts canary from results (server→client)
poison server (poison_server.py)  — read_notes description contains the attack`


## Results
| Experiment | Result |
| --- | --- |
| No guard, think:False (5 runs) | 0/5 canaries leaked; 1 hallucinated compliance (model *claimed* it fetched config, never did) |
| No guard, think:True (3 runs) | **1/3 full exfiltration**, secrecy instruction obeyed |
| Guard v1 (broken, 4 runs) | 1/4 model obeyed poison ordering; guard 2 covered every canary |
| Guard v1 (fixed, 3 runs) | 1 GUARD line, sanitized description, 0/3 read\_config, 0/3 canaries |

### reasoning mode made the agent MORE attackable, not less.

## The bug story

the sanitizer logged 3 GUARD lines while passing the entire poison; root cause was stale state in the marker loop; lesson: test a guard's output, never trust its log lines. Mention test_guard.py fails on the 

## Limitations

blocklist markers are rewordable (Lesson 8 recurses here), canary guard only covers known secrets, single model + small samples. One line each.