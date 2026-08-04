# AI SOC Assistant (n8n)

**Status:** Implemented · **Platform:** n8n · **Nodes:** 14 · **Trigger:** Webhook (Slack Events API)

An analyst pastes a security event into a Slack channel. The workflow classifies
what kind of event it is, picks a system prompt written for that specific log
source, sends it to a locally hosted Ollama model, and replies in the thread
with a structured assessment.

| File | Purpose |
|---|---|
| [`ai-soc-assistant.sanitized.json`](ai-soc-assistant.sanitized.json) | The importable workflow export |
| [`configuration.md`](configuration.md) | Every value you must change, by node |
| [`credentials.md`](credentials.md) | Slack app setup and credential scopes |
| [`node-reference.md`](node-reference.md) | Node-by-node behaviour and data contract |
| [`testing.md`](testing.md) | Test cases and expected results |
| [`troubleshooting.md`](troubleshooting.md) | Symptoms, causes, fixes |
| [`CHANGELOG.md`](CHANGELOG.md) | Workflow version history |

## Flow

```
Webhook
   └─> Detect Input Type                (normalize Slack event)
        └─> Classifier    (loop guard + classify input_type)
             └─> Switch           (10 outputs on input_type)
                  ├─ ip        ──> (not connected)
                  ├─ hash      ──> (not connected)
                  ├─ wazuh_json ─> wazuh_json prompt ─┐
                  ├─ windows   ──> windows prompt ─┤
                  ├─ linux     ──> (not connected)
                  ├─ fortigate ──> fortigate prompt ─┤
                  ├─ paloalto  ──> paloalto prompt ─┼─> LLM (ollama) ─> Compiler ─> Send a message
                  ├─ f5        ──> f5 prompt ─┤   (Ollama)         (extract)       (Slack thread)
                  ├─ cef       ──> edr prompt ─┤
                  └─ general   ──> general prompt ─┘
```

Each `prompt` node sets exactly one field — `system_prompt` — and passes
everything else through (`includeOtherFields: true`). They are prompt selectors,
nothing more.

## What the analyst sees

A plain-text threaded reply. No Markdown — the prompts explicitly forbid it,
because Slack renders `**bold**` and backticks inconsistently inside code-heavy
security text. Format varies slightly per source but always contains:

```
🛡️ Wazuh Alert Analysis

Verdict: Requires Investigation

Severity: Low

Overall Risk: Low

Confidence: Medium

Summary
...

Evidence
• ...

Assessment
...

Recommended Actions
• ...

Missing Information
• ...
```

Full samples: [`../../../examples/outputs/`](../../../examples/outputs/).

## Supported input types

| `input_type` | Detected by | Prompt node | Wired |
|---|---|---|---|
| `windows` | `data.win`, `system.eventID`, `providerName`, decoder `windows_eventchannel`, rule groups `windows`/`windows_security`; or text containing `microsoft-windows-security-auditing`, `eventid`, `windows security` | `windows prompt` | Yes |
| `fortigate` | decoder or rule group containing `fortigate`; or text containing `fortigate`/`fortios` | `fortigate prompt` | Yes |
| `paloalto` | decoder or rule group containing `paloalto`; or text containing `palo alto`/`pan-os` | `paloalto prompt` | Yes |
| `f5` | decoder or rule group containing `f5`; or text containing `f5-bigip`/`big-ip`/`asm:` | `f5 prompt` | Yes |
| `cef` | `predecoder.program_name == "cef"` or a `CEF:0\|Trend Micro\|` header, **and** a Trend Micro product marker | `edr prompt` | Yes |
| `linux` | decoder/group `linux`, `/var/log/auth.log`, `sshd[` | — | **No** |
| `wazuh_json` | fallback for documents with `rule`, `agent`, `manager`, `cluster`, or `_index` starting `wazuh-` | `wazuh_json prompt` | Yes |
| `hash` | plain text matching a 32/40/64-char hex string | — | **No** |
| `ip` | plain text matching an IPv4 address in a message of ≤3 whitespace-separated tokens | — | **No** |
| `general` | default when nothing else matches | `general prompt` | Yes |

Classification order matters. Specific embedded log sources are tested before
the generic `wazuh_json` fallback, so a Wazuh document carrying a FortiGate log
is routed to the FortiGate analyst prompt rather than the generic one. That
ordering is a deliberate design decision, documented in the Code node's own
comments.

> **`ip`, `hash` and `linux` are dead ends.** The classifier assigns them and
> the Switch has outputs for them, but those outputs connect to nothing. An
> input classified as one of these produces **no reply**. The execution
> completes successfully and silently. This is the first item on the
> [roadmap](../../../docs/roadmap.md).

## Import

1. n8n → *Workflows* → *Import from File* → `ai-soc-assistant.sanitized.json`.
2. The workflow imports **inactive** with a placeholder Slack credential. It
   will not run until you fix both.
3. Work through [`configuration.md`](configuration.md) — four placeholders.
4. Work through [`credentials.md`](credentials.md) — one Slack credential.
5. Activate, then register the production webhook URL with your Slack app.

## Security notes specific to this workflow

- The Webhook node has **no authentication configured**. Slack signature
  verification is not implemented. Anyone with the URL can send it work. Read
  [`../../../docs/security-model.md`](../../../docs/security-model.md) before
  exposing it.
- Event text is passed to the model as a user message. Log fields are
  attacker-influenceable, so prompt injection is in scope — see
  [`../../../docs/threat-model.md`](../../../docs/threat-model.md).
- The workflow cannot block, isolate, or close anything. Its only write action
  is posting a Slack message.
