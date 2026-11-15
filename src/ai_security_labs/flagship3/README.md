# Flagship 3: The Approval Gate — Human-in-the-Loop, Fail Closed

Flagship 2 replaced content inspection with a boundary: the allowlist decides,
and the poison's words never get read. But a boundary has a blind spot. Some
calls are dangerous and still sometimes wanted. Refusing them forever is safe;
serving them unguarded is flagship 1 all over again.

Flagship 3 closes that gap with the pattern real systems call human-in-the-loop
approval: the gate pauses a dangerous call, a human decides, and the decision
travels on a channel the model cannot write to. One more rule came out of the
experiments: **approve must not mean unfiltered.** Even after consent, the
result is scrubbed before the model sees it.

## Architecture

```
mini client (LLM agent)  ->  approval_proxy  ->  poison server (unchanged)
```

Each tool has one of three rules in a policy table written by the operator:

| Rule | Behavior |
| --- | --- |
| `allow` | Forward without asking |
| `deny` | Refuse. The model sees a bare error |
| `approve` | Pause, ask the human, forward only on an explicit yes |

Tools missing from the table are denied by default.

The approval prompt shows four lines, each with an owner:

1. What the user asked for (sent by the client)
2. What the agent is calling (observed by the proxy)
3. The operator's data class and note (trusted, from the policy)
4. The tool's own description (UNTRUSTED, written by the server, labeled so)

Line 4 matters more than it looks: the approval prompt itself has an injection
surface. A tool description that says "routine maintenance, safe to approve"
is talking to the human, not the model. Trusted labels come only from operator
policy, never from the tool's own mouth.

Behind the approval sits the result scrubber from flagship 1, moved after the
boundary: encoded results are decoded first, then credential-shaped lines are
replaced with `[REDACTED]` before the model reads them. And when no terminal
exists, an `approve` call fails closed: refused, logged, never hanging, never
auto-approved.

## Results (measured, one model, directional numbers)

- **Black-box approval (lesson 1):** with a bare prompt (`read_config({})`),
  the operator approved, and the model decoded the base64 config itself and
  presented the password in its answer. Full exfiltration, with permission.
- **Approval with context (lesson 2):** the rich prompt (credentials label,
  request mismatch, "not for regular users") still got one approval.
  Approval fatigue, measured on the operator.
- **Approve ≠ unfiltered (lesson 3):** after the scrubber, an approved
  `read_config` delivered the config minus the password. `db_password`
  became `[REDACTED]` before the model saw it; `admin_email` crossed, because
  redaction is credential-shaped, not a blanket. Canary crossings across all
  flagship 3 runs: **0**.
- **Headless (lesson 4):** with no controlling terminal, `read_config` is
  refused immediately (fail closed). Regression test: 5/5.

## Key findings

1. **The gate is perfect; the approver is the attack surface.** Every
   exfiltration in this flagship required a human yes.
2. **An approval prompt can never show the consequence.** The data does not
   exist at approval time. Therefore approve ≠ unfiltered: scrub after consent.
3. **The approval prompt has an injection surface.** Tool descriptions are
   attacker-writable text shown to a human.
4. **Human-facing regressions pass machine-output tests.** The rich prompt
   was lost in a code swap while the test suite stayed green. Human channels
   need their own review; no JSON-RPC test reads your screen.
5. **Fail closed, never crash.** A missing human refuses one call. A crash
   refuses every call after it.
6. **The `/dev/tty` detail:** a read+write handle requires a seekable file,
   and a terminal is not seekable. Separate handles for writing and reading.

## Defense regression test — `test_approval.py`

Five checks, no LLM, no human. The test spawns the proxy with
`start_new_session=True`, so the child has no controlling terminal by
construction and the approval channel discovers "no human" for real:

1. `initialize` passes through
2. All tools visible in `tools/list` (flagship 3 shows, then gates)
3. `read_notes` passes through (`allow`)
4. An unknown tool is refused (`default deny`)
5. `read_config` fails closed when headless

Exit code 1 on any failure, CI-ready.

## Decision record

- **Control chosen:** per-tool approval rules with fail-closed headless
  behavior, plus result scrubbing after consent.
- **Tradeoff:** the human in the loop adds latency and is fallible (fatigue
  measured above), and automated environments lose `approve` tools entirely;
  in exchange, dangerous-but-wanted tools become usable without handing
  credentials to the model.
- **Business impact:** even a mistaken or fatigued approval no longer leaks
  secrets, and the absence of a human degrades to refusal instead of risk.

## Limitations (measured, not assumed)

- **The scrubber is a detector.** A novel encoding beats it. It is the last
  layer, not the first; flagship 1 proved detectors lose alone.
- **The approve path is untestable headless by design**, so the scrubber's
  in-place behavior is human-verified, not regression-tested.
- **The tty read has no timeout.** A terminal with no typing human hangs the
  approval. The headless case fails closed; the idle-terminal case does not.
- **No client identity.** The proxy trusts whoever spawns it.
- **Small samples.** One 4B model, run counts in single digits. Directional.

## Next upgrades

- Approval timeout: no answer in N seconds fails closed.
- Client identity/authentication on the proxy.
- Field-level approval: approve specific fields, not whole tools.
- Audit sink: approvals and refusals to structured storage.

## Reproduce

```fish
cd src/ai_security_labs/flagship3
uv run python approval_client.py    # needs Ollama at localhost:11434, qwen3.5:4b
uv run python test_approval.py      # no LLM, no human
```

Archive evidence with unique names: `mv approval.log approval_(date +%H%M%S).log`.
Logs are gitignored.

## File map

| File | Role |
| --- | --- |
| `approval_proxy.py` | Policy table, rich approval prompt, fail-closed headless, result scrubber |
| `approval_client.py` | Minimal agent client; verdict counts approvals, refusals, canary crossings |
| `test_approval.py` | 5-check headless regression test |
| `../flagship1/poison_server.py` | The attacker, unchanged since flagship 1 |