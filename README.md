# AI Security Labs

Hands-on AI security learning lab: every lesson is a small, working, tested experiment.
Built from scratch on CachyOS (Arch Linux), Python 3.12 + uv, local models via Ollama
(qwen3.5:4b on an RTX 4050) — plus a cloud client for Mistral's API.

## Lessons 1–5: Foundations
GitHub repo and git workflow, uv project skeleton, cloud LLM client (Mistral API),
local LLM client (Ollama), first prompt-injection experiment.

## Project 1: Prompt Injection Attack & Defense Lab (lessons 6–10)

A local store-support bot holds a secret in its system prompt. I attacked it with an
escalation suite, measured what worked, then built a defense-in-depth pipeline and
proved it with automated verdicts.

### Architecture
`user message → input filter (keyword blocklist) → LLM (local) → output guard
(secret scan + redaction) → user`

### Method
- Escalation suite: direct override, fake authority, story misdirection, prompt dump
- Bypass suite: rephrasing, character spacing, homoglyph substitution
- Verdicts computed in code (substring leak detection), never by eye
- Suites repeated across runs, because LLMs are probabilistic: results are rates, not facts

### Results (qwen3.5:4b, local)
   Test | Result |
 |---|---|
 | Naive attacks vs input filter | 4/4 blocked |
 | Crafted attacks vs input filter | 0/15 blocked |
 | Model-level leak rate under crafted attacks | ~47% (7/15) |
 | Secrets reaching the user after output guard | 0 |
 | Benign messages blocked by filter (false positives) | 1/3 |

### Known limitations (v1)
1. The output guard redacts only the known secret — the system prompt itself can still leak through it.
2. The keyword blocklist both over-blocks innocents ("Secret Santa") and misses rephrased attacks.

### Next upgrades
- Output-side detection for system-prompt leakage
- Replace the blocklist with intent classification
- Multi-turn attack chains

### Files
- `src/ai_security_labs/lesson6_injection.py` — first injection experiment
- `src/ai_security_labs/lesson7_escalation.py` — escalation suite + automated verdicts
- `src/ai_security_labs/lesson8_filter_v1.py` — input filter, tested both ways
- `src/ai_security_labs/lesson9_bypass.py` — filter bypass suite
- `src/ai_security_labs/lesson10_guard.py` — full defense-in-depth pipeline