# Data flow

What data exists at each stage, and what it contains.

Diagram source: [`../diagrams/data-flow.mmd`](../diagrams/data-flow.mmd).

## Stage by stage

### 1. Analyst message (Slack)

An analyst pastes a Wazuh alert, a raw log line, an IOC, or a question. This is
the highest-sensitivity data in the system: internal hostnames, usernames,
private addressing, file paths, process command lines, and often the live shape
of an incident.

It already resides in Slack — a third-party SaaS — before this workflow sees it.

### 2. Webhook payload

Slack POSTs an `event_callback` envelope. The Webhook node exposes it as
`$json.body`.

```json
{ "body": { "event": { "type": "message", "text": "<the pasted event>",
  "channel": "C0EXAMPLE001", "user": "U0EXAMPLE001", "ts": "1735689600.000100" } } }
```

Sample: [`../examples/inputs/slack-event.json`](../examples/inputs/slack-event.json).

### 3. Normalized item (`Detect Input Type`)

```json
{ "message": "<the pasted event>", "channel": "C0EXAMPLE001",
  "user": "U0EXAMPLE001", "thread_ts": "1735689600.000100",
  "=event_type": "message" }
```

The original `body` is dropped here — this Set node does not pass other fields
through. The field named `=event_type` genuinely carries a leading `=`; see
[`../workflows/n8n/ai-soc-assistant/node-reference.md`](../workflows/n8n/ai-soc-assistant/node-reference.md).

Schema: [`../schemas/normalized-alert.schema.json`](../schemas/normalized-alert.schema.json).

### 4. Classified item (`Classifier`)

Adds one field:

```json
{ "...": "...", "input_type": "fortigate" }
```

Or produces **no item at all** if the loop guard fired.

### 5. Prompted item (prompt node)

Adds `system_prompt` — between ~1.6 KB and ~31 KB of analyst instructions.
Everything else passes through, which is how `channel` and `thread_ts` survive
to the delivery stage.

### 6. Inference request

```json
{ "model": "OLLAMA_MODEL", "stream": false,
  "messages": [ { "role": "system", "content": "<system_prompt>" },
                { "role": "user", "content": "<message>" } ] }
```

The user message is the analyst's raw text, unescaped and undelimited. This is
the prompt-injection surface —
[`threat-model.md`](threat-model.md#t4--prompt-injection-via-log-content).

### 7. Inference response

```json
{ "model": "...", "message": { "role": "assistant", "content": "<report text>" },
  "done": true }
```

### 8. Delivery item (`Compiler`)

```json
{ "response": "<report text>", "channel": "C0EXAMPLE001",
  "thread_ts": "1735689600.000100" }
```

`channel` and `thread_ts` are pulled back from `Detect Input Type` by name,
because the Ollama response carries no routing information.

**No parsing or validation occurs.** Whatever the model produced is what the
analyst sees.

### 9. Slack reply

Plain text, posted in-thread. Sample:
[`../examples/outputs/slack-triage-message.txt`](../examples/outputs/slack-triage-message.txt).

## Where data comes to rest

| Location | Contents | Retention |
|---|---|---|
| Slack | Original event and the assessment | Workspace retention policy |
| n8n execution history | **Every field above**, including full event text and full prompts | Until pruned — see [`observability.md`](observability.md) |
| Ollama | Request in memory during inference | Not persisted by default; check your logging configuration |
| This repository | Nothing. Only synthetic examples. | — |

The n8n execution history row is the one people miss. It is a complete,
searchable archive of every security event anyone has ever pasted into the
channel.

## Data that never flows

| Destination | Status |
|---|---|
| VirusTotal, AbuseIPDB | No call. Planned. |
| TheHive, Cortex, OpenCTI | No call. Planned. |
| Firewalls, EDR, IAM | **No write path exists in any form.** |
| Any hosted inference API | Not unless `OLLAMA_BASE_URL` is repointed — which is a data protection decision, not a configuration tweak. |

## Normalized structures

Two schemas describe shapes that do not exist in the current workflow but are
defined so that examples and future implementation agree:

- [`enrichment-result.schema.json`](../schemas/enrichment-result.schema.json) —
  planned enrichment output
- [`ai-triage-result.schema.json`](../schemas/ai-triage-result.schema.json) —
  planned parsed triage output

Both are labelled `PLANNED` in their own `description` fields.
