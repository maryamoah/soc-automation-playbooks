# Testing

How to verify the workflow works, and — more importantly — how to check that it
fails safely.

Repository-wide strategy: [`../../../docs/testing-strategy.md`](../../../docs/testing-strategy.md).

---

## Repository checks (no n8n required)

```bash
python3 scripts/validate_json.py          # every .json parses; export structure sane
python3 scripts/validate_examples.py      # examples conform to schemas/
python3 scripts/scan_sensitive_values.py  # no secrets, private IPs, tokens, ngrok URLs
```

All three run in CI. They validate the repository, not the deployment — a clean
run means the export is well-formed and sanitized, not that your Ollama host is
up.

---

## Pre-flight

Before testing the workflow end to end:

```bash
# 1. Ollama reachable and the model present
curl -s http://<ollama-host>:11434/api/tags | grep '"name"'

# 2. Inference works at all, from the n8n host
curl -s http://<ollama-host>:11434/api/chat -d '{
  "model": "qwen3:14b",
  "stream": false,
  "messages": [{"role":"user","content":"Reply with the word OK."}]
}' | head -c 400

# 3. Slack token valid
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  https://slack.com/api/auth.test
```

If step 2 fails from the n8n host, no amount of workflow debugging will help.

---

## Testing without Slack

The Webhook node accepts any JSON body, so you can drive the workflow with
`curl` and watch it in the n8n execution log. Replies will fail at the Slack
node unless `channel` is a real ID — that is fine; everything up to and
including inference still executes and is visible.

Use the n8n **test** URL (`/webhook-test/<path>`) with *Listen for test event*
active in the editor.

```bash
N8N_TEST_URL="https://<n8n-host>/webhook-test/<your-path>"

curl -sS -X POST "$N8N_TEST_URL" \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "body": {
    "event": {
      "type": "message",
      "text": "Wazuh rule 5710 fired on host WEB-01. sshd[24601]: Failed password for invalid user admin from 192.0.2.10 port 51244 ssh2",
      "channel": "C0EXAMPLE001",
      "user": "U0EXAMPLE001",
      "ts": "1735689600.000100"
    }
  }
}
JSON
```

Note the `body` wrapper. Slack's HTTP POST body becomes `$json.body` inside the
Webhook node, so a hand-built payload must nest the event the same way, or
`Detect Input Type` produces empty strings.

The example events in [`../../../examples/inputs/`](../../../examples/inputs/)
are already in this shape and can be posted directly with `-d @file`.

---

## Test cases

The `Expected input_type` column is the assertion that matters — check it on the
Code node's output in the execution view before judging the model's answer.

| # | Input | Expected `input_type` | Expected result |
|---|---|---|---|
| 1 | [`wazuh-windows-alert.json`](../../../examples/inputs/wazuh-windows-alert.json) | `windows` | `🪟 Windows Event Analysis`. Kerberos 4768 / result `0x6` on a computer account. Should **not** claim credential theft or Kerberoasting. |
| 2 | [`wazuh-firewall-alert.json`](../../../examples/inputs/wazuh-firewall-alert.json) | `fortigate` | `🔥 FortiGate Security Analysis`. Traffic was **denied**. Must not describe it as a successful compromise; Overall Risk should be Low. |
| 3 | [`wazuh-rule-id-only-alert.json`](../../../examples/inputs/wazuh-rule-id-only-alert.json) | `wazuh_json` | `Requires Investigation`, low confidence, a substantial `Missing Information` list. **No verdict may be asserted from a rule ID alone.** |
| 4 | Free text: `What is the difference between Kerberoasting and AS-REP roasting?` | `general` | Conversational answer, no verdict block, under ~1500 characters. |
| 5 | Bare IP: `192.0.2.10` | `ip` | **No reply at all.** This is the known dead-end route — see below. |
| 6 | Bare hash: `44d88612fea8a8f36de82e1278abb02f` | `hash` | **No reply at all.** Same dead-end route. |

### Cases 5 and 6 are the important ones

They are not decoration. They document a real defect: the classifier assigns
`ip` and `hash`, the Switch has outputs for them, and those outputs connect to
nothing. The execution **succeeds**, the analyst gets **silence**, and there is
no error anywhere to notice.

When you run these, confirm the failure mode you actually have:

1. Open the execution in n8n. It should be green/successful.
2. The Switch node shows an item leaving on output 0 (`ip`) or 1 (`hash`).
3. Nothing runs after it.

If you have wired those outputs (roadmap item 1), update this table — and update
[`../../../README.md`](../../../README.md#known-limitations) with it.

The same applies to `linux` (Switch output 4). Note that most Linux events
arriving as Wazuh JSON hit the `linux` branch *before* the `wazuh_json`
fallback, so a genuine SSH brute-force alert in Wazuh format can vanish
silently. Test it:

```bash
curl -sS -X POST "$N8N_TEST_URL" -H 'Content-Type: application/json' \
  -d '{"body":{"event":{"type":"message","text":"{\"_source\":{\"rule\":{\"id\":\"5710\",\"groups\":[\"linux\",\"sshd\"]},\"decoder\":{\"name\":\"sshd\"}}}","channel":"C0EXAMPLE001","user":"U0EXAMPLE001","ts":"1735689600.000100"}}}'
```

Expected today: classified `linux`, routed to output 4, no reply.

---

## Loop-guard tests

The guard is the difference between a helpful bot and a runaway one. Test all
three conditions.

| Payload fragment in `body.event` | Expected |
|---|---|
| `"bot_id": "B0EXAMPLE001"` | Code node returns `[]`; nothing downstream runs |
| `"subtype": "bot_message"` | Same |
| `"user": "<your configured bot ID>"` | Same |

```bash
curl -sS -X POST "$N8N_TEST_URL" -H 'Content-Type: application/json' \
  -d '{"body":{"event":{"type":"message","subtype":"bot_message","bot_id":"B0EXAMPLE001","text":"test","channel":"C0EXAMPLE001","ts":"1735689600.000200"}}}'
```

The execution should complete with the Code node emitting zero items. If
anything runs after it, stop and fix the guard before activating in a live
channel — a self-answering loop will saturate your GPU and flood the channel.

---

## What to check in the model's answer

Format compliance is easy to eyeball; analytic discipline is what actually
matters. For every investigation-type response, check:

- **Blocked ≠ breached.** If the event shows a deny or a block, the answer must
  not describe successful access, execution or compromise.
- **Metadata is not evidence.** Rule name, rule level, fired-times and MITRE
  mappings may explain why the alert fired. They must not be presented as proof
  that a technique executed.
- **MITRE only where the evidence supports it.** A technique named in the answer
  should be traceable to something observable in the event.
- **Private IPs are not automatically trusted**, and public destinations are not
  automatically hostile.
- **Uncertainty resolves to `Requires Investigation`**, not to a guess.
- **`Missing Information` is populated** with things that would actually change
  the verdict.
- **Evidence contains only observable facts** — no interpretation, no rule
  descriptions, no assumptions.
- **Plain text.** No `**`, no backticks, no Markdown headings, no tables.

A response that is beautifully formatted and analytically wrong is worse than a
messy correct one, because it is more persuasive. Weight your review
accordingly.

---

## Regression testing after changes

Re-run all six cases after any of these:

- Editing a system prompt
- Changing `OLLAMA_MODEL`
- Upgrading Ollama or n8n
- Modifying the classifier

Prompt edits are the highest-risk change here. These prompts encode a large
number of negative constraints — "do not conclude X", "never treat Y as proof" —
and it is easy to delete a guard rail while tidying wording. Diff the prompt
before and after, and specifically re-run cases 2 and 3, which exist to catch
over-claiming.

Record results — date, model, six outcomes, notable deviations. Model behaviour
drifts between versions, and without a baseline you cannot tell whether an
upgrade helped.

---

## Load and cost

Not implemented, worth knowing: there is no rate limiting, no queue bound, and
no cost control. Every message in a channel the bot is in becomes an inference
request. Before deploying to a busy channel, measure single-request latency at
your largest prompt (the Palo Alto one, ~31 KB) and decide what concurrency your
hardware tolerates. `N8N_CONCURRENCY_PRODUCTION_LIMIT` is the blunt instrument
available today.
