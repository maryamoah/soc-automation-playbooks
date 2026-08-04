# Node reference

Every node in `ai-soc-assistant.sanitized.json`, in execution order, with the
data contract between them. This document describes the workflow **as shipped**.
Where behaviour is surprising or looks like a defect, it is documented rather
than quietly corrected.

Node names are the raw n8n defaults (`Detect Input Type`, `Compiler`, …). They are
preserved because expressions inside the workflow reference them by name — for
example `$('Detect Input Type').item.json.channel` in `Compiler`. Renaming a node
in the n8n editor updates those references automatically; editing the JSON by
hand does not. See [Renaming nodes](#renaming-nodes).

---

## 1. `Webhook`

| | |
|---|---|
| Type | `n8n-nodes-base.webhook` (v2.1) |
| Method | `POST` |
| Path | `ai-soc-assistant` *(placeholder — change it)* |
| Auth | **None configured** |
| Response | Default (`onReceived`, immediate `200`) |

The entry point. Built for Slack Events API delivery, but it accepts any JSON
body — which is what makes `curl` testing possible without Slack.

Production URL is `https://<your-n8n-host>/webhook/<path>`; the test URL is
`/webhook-test/<path>` and only listens while you have the editor open in
"Listen for test event" mode.

**Slack URL verification:** when you first register the URL, Slack sends a
`{"type": "url_verification", "challenge": "..."}` payload and expects the
challenge echoed back. This workflow **does not implement that handshake** —
the default node response returns `{"message": "Workflow was started"}`, which
Slack rejects. Work around it as described in
[`credentials.md`](credentials.md#url-verification).

**Security:** no authentication, no signature check, no rate limit. This is the
workflow's largest exposure. See
[`../../../docs/security-model.md`](../../../docs/security-model.md).

---

## 2. `Detect Input Type` — normalize the Slack event

| | |
|---|---|
| Type | `n8n-nodes-base.set` (v3.4) |
| Passthrough | No (`includeOtherFields` not set) |

Flattens the Slack event envelope into five top-level fields:

| Output field | Expression | Notes |
|---|---|---|
| `message` | `{{ $json.body.event.text }}` | The pasted event — the thing to analyze |
| `channel` | `{{ $json.body.event.channel }}` | Carried through for the reply |
| `user` | `{{ $json.body.event.user }}` | Used by the loop guard |
| `thread_ts` | `{{ $json.body.event.thread_ts \|\| $json.body.event.ts }}` | Reply in the existing thread if there is one, otherwise start one on the message |
| `=event_type` | `{{ $json.body.event.type }}` | **Field name begins with a literal `=`** |

### The `=event_type` field name

The fifth assignment's *name* is `=event_type`, not `event_type`. In the n8n Set
node the `=` prefix belongs on the **value** to mark it as an expression; here it
has also been typed into the name box. The resulting item therefore has a key
literally spelled `=event_type`.

This is preserved as-is. Nothing downstream reads it — the classifier and Switch
use `input_type`, not `event_type` — so the workflow behaves correctly despite
it. If you intend to filter on Slack event type later, fix the field name first.
See [`troubleshooting.md`](troubleshooting.md#the-event_type-field-has-a-stray--prefix).

**Note the passthrough setting.** This node does *not* pass other fields
through, so the original `body` is dropped from the item at this point. The
Code node handles that: it reads `$json.body?.event ?? $json`, so when `body` is
absent it falls back to the flattened item.

---

## 3. `Classifier` — loop guard and classifier

| | |
|---|---|
| Type | `n8n-nodes-base.code` (v2) |
| Mode | Run once for all items (default) |

Two responsibilities.

### 3a. Loop guard

```js
const slackEvent = $json.body?.event ?? $json;
const eventUser  = slackEvent?.user ?? $json.user ?? '';

if (slackEvent?.bot_id ||
    slackEvent?.subtype === 'bot_message' ||
    eventUser === 'SLACK_BOT_USER_ID') {
  return [];
}
```

Returning an empty array ends the branch with no items, so nothing downstream
runs. Without this, the bot's own reply would arrive back through the Events API
as a new message and the workflow would answer itself indefinitely.

Three independent checks, because Slack is inconsistent about which one it
sends: `bot_id` is present on most bot posts, `subtype: "bot_message"` on
others, and the explicit user-id comparison catches messages posted as a user
token. **`SLACK_BOT_USER_ID` is a placeholder** — replace it with your bot's
actual member ID or the guard cannot fire on the third condition. See
[`configuration.md`](configuration.md).

### 3b. Input classification

Reads the first non-empty of `$json.message`, `$json.text`, `$json.body`,
`$json.input`, then attempts `JSON.parse` if the value is a string. Two
classification paths follow.

**Structured path** (input parsed to an object). Reads `parsed._source ?? parsed`,
then examines `decoder.name`, `predecoder.program_name`, `rule.groups`,
`data.win`, and `_index`. Tests run in this order — first match wins:

1. `windows` — any of `data.win`, `data.win.system.eventID`,
   `data.win.system.providerName`, decoder `windows_eventchannel`, rule group
   `windows` or `windows_security`
2. `fortigate` — decoder contains `fortigate`, a rule group contains
   `fortigate`, or the serialized text contains `fortigate`
3. `paloalto` — decoder or group contains `paloalto`, or text contains
   `palo alto` / `pan-os`
4. `f5` — decoder or group contains `f5`, or text contains `f5-bigip` /
   `big-ip`
5. `cef` — a CEF marker (`program_name == "cef"`, or a `CEF:0|Trend Micro|`
   header with or without a space) **and** a Trend Micro product marker
   (group `trendmicro`, `|trend micro|`, `deep security`,
   `deep discovery inspector`, `apex central`, `apex one`)
6. `linux` — decoder or group `linux`, or text containing `/var/log/auth.log`
   or `sshd[`
7. `wazuh_json` — fallback for anything carrying `rule`, `agent`, `manager`,
   `cluster`, or an `_index` starting with `wazuh-`

The ordering is the point. A Wazuh alert wrapping a FortiGate log matches both
rule 2 and rule 7; testing specific sources first means it reaches the FortiGate
analyst prompt. The source comments in the node say so explicitly: *"Check
specific embedded log sources first. Do not classify every Wazuh document as
wazuh_json."*

**Text path** (input is not JSON). Same source detection against lowercased
text, plus two IOC checks at the end:

- `hash` — the trimmed text matches `[a-f0-9]{32}`, `{40}` or `{64}`
  (MD5 / SHA-1 / SHA-256), case-insensitive
- `ip` — the trimmed text contains an IPv4 address **and** is at most three
  whitespace-separated tokens. The token limit is what stops a full log line
  containing an IP being misclassified as a bare IOC.

Default when nothing matches: `general`.

**Output:** the original item plus `input_type`.

```json
{ "message": "...", "channel": "...", "user": "...", "thread_ts": "...", "input_type": "windows" }
```

---

## 4. `Route Investigation`

| | |
|---|---|
| Type | `n8n-nodes-base.switch` (v3.4) |
| Rules | 10, all `$json.input_type` string-equals, strict type validation |
| Fallback | None configured |

| Output | `input_type` | Connected to |
|---|---|---|
| 0 | `ip` | **nothing** |
| 1 | `hash` | **nothing** |
| 2 | `wazuh_json` | `wazuh_json prompt` |
| 3 | `windows` | `windows prompt` |
| 4 | `linux` | **nothing** |
| 5 | `fortigate` | `fortigate prompt` |
| 6 | `paloalto` | `paloalto prompt` |
| 7 | `f5` | `f5 prompt` |
| 8 | `cef` | `edr prompt` |
| 9 | `general` | `general prompt` |

Outputs 0, 1 and 4 are unconnected. Items routed there stop, the execution
finishes as successful, and the analyst receives **nothing** — no reply, no
error. Because there is also no fallback output, this is silent rather than
loud.

Wiring these three is [roadmap item 1](../../../docs/roadmap.md). The cheapest
interim mitigation is to add a fallback output to `general prompt` (the general
prompt), so unhandled types at least get an answer.

---

## 5. Prompt selection nodes

| | |
|---|---|
| Type | `n8n-nodes-base.set` (v3.4) |
| Passthrough | **Yes** (`includeOtherFields: true`) |
| Sets | `system_prompt` (string) |

Seven nodes, structurally identical, differing only in prompt text. Because
passthrough is on, `message`, `channel`, `thread_ts` and `input_type` survive
into the LLM (ollama) node — which is what lets the Slack reply find its way
back to the right thread.

| Node | Route | Prompt length | Report heading |
|---|---|---|---|
| `general prompt` | `general` | ~1.6 KB | *(no heading — conversational answer)* |
| `wazuh_json prompt` | `wazuh_json` | ~7.4 KB | `🛡️ Wazuh Alert Analysis` |
| `windows prompt` | `windows` | ~10.6 KB | `🪟 Windows Event Analysis` |
| `fortigate prompt` | `fortigate` | ~22.1 KB | `🔥 FortiGate Security Analysis` |
| `paloalto prompt` | `paloalto` | ~31.2 KB | `Palo Alto Security Analysis` |
| `f5 prompt` | `f5` | ~9.3 KB | `F5 BIG-IP ASM / Advanced WAF Security Analysis` |
| `edr prompt` | `cef` | ~17.2 KB | `Trend Micro Security Analysis` |

### What the prompts share

All six investigation prompts (everything except `general`) impose the same
analytic discipline:

- **Verdict vocabulary:** `Malicious`, `Suspicious`, `Benign`,
  `False Positive`, `Requires Investigation` — with `Requires Investigation`
  mandated whenever evidence is ambiguous.
- **Severity:** `Informational`, `Low`, `Medium`, `High`, `Critical`.
- **Overall Risk** is separated from **Severity**, and both are separated from
  the source rule's own level. The Wazuh prompt states it directly: a high
  severity alert for blocked activity with no evidence of compromise is
  *Overall Risk: Low*.
- **Confidence** reflects evidence quality, not alert severity.
- **Detection metadata is not evidence.** Rule ID, rule name, rule level,
  fired-times count, alert groups and MITRE mappings explain why an alert fired.
  The prompts forbid treating them as proof that anything happened.
- **Denied traffic is not malicious by default; allowed traffic is not benign
  by default.** Repeated blocked connections alone do not establish
  reconnaissance, scanning, exploitation, malware, C2 or compromise.
- **Sections:** `Summary`, `Evidence`, `Assessment`, `Recommended Actions`,
  `Missing Information` — where `Evidence` may contain only directly observable
  facts, and `Missing Information` must state what would raise confidence.
- **Plain text only.** No Markdown, HTML, tables, code blocks or numbered lists;
  `•` for bullets; one blank line between sections.

Source-specific additions worth knowing: the Wazuh prompt carries an explicit
rule-level-to-severity mapping (0–2 Informational, 3–5 Low, 6–9 Medium, 10–12
High, 13–16 Critical) and forbids printing the numeric level. The Windows prompt
covers Kerberos failure codes and their common non-malicious causes, and
requires `Account Type: Computer Account` when an account name ends in `$`. The
FortiGate and Palo Alto prompts cover NAT interpretation, session end reasons,
zones and application-risk fields. The F5 prompt separates *alerted* from
*blocked* from *passed*, and separates HTTP response codes from WAF actions. The
Trend Micro prompt distinguishes product and module before assigning a verdict.

The `general` prompt is different in kind: it answers cybersecurity questions
conversationally for Slack, under 1500 characters, and does not produce a
verdict block.

Read them in full in the export — they are the substance of this project, not
boilerplate.

---

## 6. `LLM (ollama)` — Ollama inference

| | |
|---|---|
| Type | `n8n-nodes-base.httpRequest` (v4.3) |
| Method | `POST` |
| URL | `OLLAMA_BASE_URL/api/chat` *(placeholder — replace)* |
| Body | JSON, built by expression |
| Auth | None |
| Options | Default — **no timeout, no retry** |

```js
{{ JSON.stringify({
  model: "qwen3:14b",
  stream: false,
  messages: [
    { role: "system", content: $json.system_prompt },
    { role: "user",   content: $json.message }
  ]
}) }}
```

Two configuration points live here: the URL and the `model` value inside the
body expression. Both are covered in [`configuration.md`](configuration.md).

`stream: false` is required — the downstream node reads a single complete
response object, and streaming would deliver a sequence of partial chunks it
cannot assemble.

**The user message is raw analyst-supplied text.** It is not escaped, filtered
or delimited from the system prompt beyond the role boundary. Log content is
attacker-influenceable, so this is the prompt-injection surface; see
[`../../../docs/threat-model.md`](../../../docs/threat-model.md#t4--prompt-injection-via-log-content).

**No error handling.** Ollama's `/api/chat` on a 14B model can take tens of
seconds. If it exceeds n8n's default timeout, or the host is unreachable, or the
model name is not pulled, the execution fails and the analyst receives silence.
Adding a timeout, retry, and error branch is
[roadmap item 6](../../../docs/roadmap.md).

**Expected response** (Ollama chat, non-streaming):

```json
{
  "model": "OLLAMA_MODEL",
  "created_at": "2024-01-01T00:00:00Z",
  "message": { "role": "assistant", "content": "🪟 Windows Event Analysis\n\nVerdict: ..." },
  "done": true,
  "total_duration": 0,
  "eval_count": 0
}
```

---

## 7. `Compiler` — extract the reply

| | |
|---|---|
| Type | `n8n-nodes-base.set` (v3.4) |
| Passthrough | No |

| Output field | Expression |
|---|---|
| `response` | `{{ $json.message.content }}` |
| `channel` | `{{ $('Detect Input Type').item.json.channel }}` |
| `thread_ts` | `{{ $('Detect Input Type').item.json.thread_ts }}` |

The two `$('Detect Input Type')` lookups reach back across the whole workflow to the
normalization node, because the Ollama response body contains no Slack routing
information. This is why `Detect Input Type` must keep its name — see
[Renaming nodes](#renaming-nodes).

**No parsing or validation happens here.** `message.content` is taken as an
opaque string. If the model ignored the format instructions, emitted Markdown,
or produced a `<think>` block, that text goes straight to Slack. Structured
parsing against
[`../../../schemas/ai-triage-result.schema.json`](../../../schemas/ai-triage-result.schema.json)
is [roadmap item 2](../../../docs/roadmap.md).

---

## 8. `Send a message` — Slack reply

| | |
|---|---|
| Type | `n8n-nodes-base.slack` (v2.4) |
| Credential | `slackApi` — placeholder `SLACK_CREDENTIAL_ID` |
| Select | `channel` |
| Channel ID | `{{ $json.channel }}` (mode: `id`) |
| Text | `{{ $json.response }}` |
| `thread_ts` | `{{ $json.thread_ts }}` |
| `includeLinkToWorkflow` | `false` |

Posts into the originating thread. `includeLinkToWorkflow: false` matters:
leaving it on appends an n8n instance URL to every message, which leaks internal
infrastructure into a channel that may include contractors or guests.

Channel is resolved by ID from the inbound event rather than being pinned to a
configured channel, so the assistant answers wherever it is invited. Requires
`chat:write` on the bot token, and the bot must be a member of that channel.

---

## Data contract summary

| After node | Item shape |
|---|---|
| `Webhook` | `{ headers, params, query, body }` — Slack envelope in `body` |
| `Detect Input Type` | `{ message, channel, user, thread_ts, "=event_type" }` |
| `Classifier` | above `+ { input_type }` — or `[]` if loop-guarded |
| `Route Investigation` | unchanged, routed to one output |
| `prompt` | above `+ { system_prompt }` |
| `LLM (ollama)` | Ollama response: `{ model, created_at, message: { role, content }, done, ... }` |
| `Compiler` | `{ response, channel, thread_ts }` |
| `Send a message` | Slack API response |

Schemas for the normalized item and the target triage structure are in
[`../../../schemas/`](../../../schemas/).

---

## Renaming nodes

Two expressions reference the node named `Detect Input Type` by name:

- `Compiler.channel` → `$('Detect Input Type').item.json.channel`
- `Compiler.thread_ts` → `$('Detect Input Type').item.json.thread_ts`

Rename it in the n8n editor and both references update automatically. Rename it
by editing the JSON and the workflow breaks at runtime with a "node not found"
error.

The node names in this export match the names used on the live canvas
(`Detect Input Type`, `Classifier`, `Route Investigation`, `LLM (ollama)`,
`Compiler`, and one `* prompt` node per route) rather than n8n's defaults. If
you rename further, do it in the editor and re-export.
