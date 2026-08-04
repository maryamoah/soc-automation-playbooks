# Troubleshooting

Symptoms, likely causes, and fixes. Start with the n8n execution list — most
questions are answered by whether an execution exists at all.

| Was there an execution? | Look at |
|---|---|
| No execution | Slack → webhook delivery. [Nothing happens](#nothing-happens-at-all) |
| Execution, no reply | The loop guard or a dead-end route. [Silent success](#execution-succeeds-but-no-slack-reply) |
| Execution failed | The node that went red. [Failures](#execution-fails) |
| Reply arrives, content wrong | [Output quality](#output-problems) |

---

## Nothing happens at all

### No execution appears in n8n

**The workflow is inactive.** Only the production URL (`/webhook/<path>`) works
when active; the test URL (`/webhook-test/<path>`) works only while the editor
is open and listening. Activate it.

**Slack never verified the URL.** Check *Event Subscriptions* in your app config
— it must show *Verified*. This workflow does not answer the `url_verification`
challenge; see [`credentials.md`](credentials.md#url-verification).

**The bot is not in the channel.** Without membership it receives no
`message.channels` events. `/invite @your-bot-name`.

**Missing scopes.** `channels:history` for public channels, `groups:history` for
private. Adding a scope requires reinstalling the app to the workspace.

**n8n is not reachable from Slack.** Slack must reach your n8n over HTTPS on a
publicly resolvable name. Check the app's *Event Subscriptions* page for
delivery failures, and your reverse proxy access log for POSTs from Slack.

**Path mismatch.** The path in the Webhook node must match the tail of the
registered request URL exactly.

---

## Execution succeeds but no Slack reply

This is the workflow's characteristic failure. A green execution with no output
almost always means one of two things.

### The loop guard fired

Expected for bot messages. Open the execution, click `Classifier` — if
it output zero items, the guard did its job. Confirm the message was actually
from a bot; if a human message is being dropped, check that
`SLACK_BOT_USER_ID` was replaced with your bot's ID and not, say, a human
user's.

### The item hit a dead-end Switch output

Outputs 0 (`ip`), 1 (`hash`) and 4 (`linux`) are **connected to nothing**. Items
routed there stop. The execution is marked successful and the analyst gets
silence.

Diagnose: open the execution, click `Route Investigation`, and see which output the item
left on.

Two fixes:

- **Interim.** Add a fallback and wire the three unused outputs to
  `general prompt` (the general prompt). An imperfect answer beats silence.
- **Proper.** Build dedicated prompt nodes for IOC lookups and Linux/auth
  events. [Roadmap item 1](../../../docs/roadmap.md).

Note the ordering interaction: a Wazuh alert whose rule groups include `linux`
is classified `linux`, *not* `wazuh_json`, because the specific check runs
first. SSH brute-force alerts in Wazuh JSON therefore disappear silently today.

### Slack rejected the post

If `Send a message` ran but nothing appeared, read its output.

| Slack error | Cause |
|---|---|
| `not_in_channel` | Bot not invited to the channel |
| `channel_not_found` | `channel` empty or malformed — check `Detect Input Type` output |
| `invalid_auth` / `token_revoked` | Token rotated or app reinstalled; recreate the credential |
| `missing_scope` | `chat:write` not granted |
| `msg_too_long` | Over 40,000 characters — see [Response truncated](#response-truncated-or-rejected) |

---

## Execution fails

### `Detect Input Type` outputs empty strings

The payload was not shaped like a Slack event. `Detect Input Type` reads
`$json.body.event.*`, so a hand-built test payload must nest the event under
`body`:

```json
{ "body": { "event": { "type": "message", "text": "...", "channel": "C0EXAMPLE001", "user": "U0EXAMPLE001", "ts": "1735689600.000100" } } }
```

### `LLM (ollama)` — connection refused / ECONNREFUSED / ENOTFOUND

The Ollama URL is wrong **from n8n's perspective**. Inside a container,
`localhost` is the container. Test from inside it:

```bash
docker exec -it <n8n-container> wget -qO- http://<ollama-host>:11434/api/tags
```

Also check the URL still says `OLLAMA_BASE_URL` — the shipped placeholder.

### `LLM (ollama)` — 404 with `model not found`

The model in the body expression is not pulled on that host.
`ollama pull qwen3:14b`, or change the model name. `curl .../api/tags` lists
what is available.

### `LLM (ollama)` — timeout / socket hang up

A 14B model answering a 31 KB system prompt legitimately takes 30–90 seconds on
CPU or modest GPUs. No timeout or retry is configured in the export. Set
*Options → Timeout* to 120000 ms, enable *Retry on Fail*, and consider a smaller
model or GPU offload. Watch `ollama ps` and `nvidia-smi` during a request — if
the model is running on CPU, that is your latency.

### `Compiler` — `Cannot read properties of undefined (reading 'content')`

The Ollama response had no `message.content`. Usually:

- **`stream: true` was set.** Streaming returns a sequence of partial objects;
  this workflow expects one complete response. It must stay `false`.
- The endpoint is `/api/generate`, which returns `response`, not
  `message.content`. This workflow requires `/api/chat`.
- Ollama returned an error object instead of a completion — read the raw
  `LLM (ollama)` output.

### `Compiler` — "node 'Detect Input Type' not found"

Someone renamed `Detect Input Type` by editing the JSON. The expressions
`$('Detect Input Type').item.json.channel` and `.thread_ts` reference it by name.
Rename in the n8n **editor** (which updates references) or restore the name.

### Slack credential shows red / "credentials not set"

Expected on a fresh import — the export ships a placeholder reference. Create a
real Slack API credential and select it on `Send a message`. See
[`credentials.md`](credentials.md).

---

## Output problems

### The reply contains `<think>` or reasoning text

Some models emit reasoning blocks in the response body. Nothing in this workflow
strips them. Either use a model that keeps reasoning out of `message.content`,
or strip it in `Compiler`:

```
={{ $json.message.content.replace(/<think>[\s\S]*?<\/think>/g, '').trim() }}
```

### The reply is Markdown despite the prompt forbidding it

Format adherence is a model capability. Smaller or heavily quantized models
drift back into Markdown regardless of instructions. Try a larger model, or
lower the temperature via `options` in the request body. There is no
post-processing step to enforce format — [roadmap item 2](../../../docs/roadmap.md).

### The reply asserts a compromise from blocked traffic

The most serious quality failure, and the one the prompts spend the most words
preventing. Verify first that the *right* prompt was selected — check
`input_type` in the execution. A FortiGate deny routed to the `general` prompt
loses every firewall-specific guard rail.

If the correct prompt was used and the model still over-claims, that is a model
capability limit, not a configuration error. It is exactly why the output is
advisory and why an analyst reviews it. Record the case, and see
[`../../../docs/ai-safety-and-limitations.md`](../../../docs/ai-safety-and-limitations.md).

### Wrong prompt selected

Check the Code node's `input_type` output against the rules in
[`node-reference.md`](node-reference.md#3-classifier--loop-guard-and-classifier).
Common causes: the event was pasted as free text rather than JSON so the
structured path never ran; a Wazuh document lacks the `rule.groups` entry the
classifier keys on; or a more specific rule matched first — remember the order
is windows → fortigate → paloalto → f5 → cef → linux → wazuh_json.

### Response truncated or rejected

Slack's `chat.postMessage` limit is 40,000 characters and messages over ~4,000
are visually truncated with a "show more" link. The prompts ask for concise
output, but nothing enforces a length cap. If this recurs, add a length check in
`Compiler` or split into thread replies.

### Reply lands outside the thread

`thread_ts` was empty. `Detect Input Type` computes it as
`thread_ts || ts` from the inbound event; if both were absent, the payload was
not a well-formed Slack message event.

---

## Known quirks

### The `=event_type` field has a stray `=` prefix

In `Detect Input Type`, the fifth assignment's **name** is `=event_type`. In n8n's Set
node the `=` marks a *value* as an expression; typed into the name box it
becomes part of the key. The item therefore carries a field literally named
`=event_type`.

Harmless today — nothing reads it. Fix the name before writing any expression
that depends on Slack event type, or that expression will silently resolve to
`undefined`. It is preserved in the sanitized export because this repository
ships what actually runs.

### The Switch has no fallback output

Any `input_type` outside the ten configured values would be dropped silently.
The classifier can only produce those ten today, so it cannot currently happen —
but if you extend the classifier and forget the Switch, you get silence. Add a
fallback output.

### The webhook responds before analysis completes

The Webhook node responds immediately (`onReceived`), which is correct: Slack
requires a response within three seconds and inference takes far longer. The
consequence is that HTTP status tells you nothing about whether the analysis
worked. Judge success by the Slack reply and the execution log, never by the
webhook's 200.
