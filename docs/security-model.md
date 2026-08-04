# Security model

What this system protects, what it does not, and where the sharp edges are.

## Trust boundaries

| Boundary | Crossing | Controls today |
|---|---|---|
| Slack → n8n | Security event text | **None.** No authentication, no signature verification. |
| n8n → Ollama | System prompt + event text | Network placement only. No authentication. |
| Ollama → n8n | Model output | None. Output is not validated or sanitised. |
| n8n → Slack | Assessment text | Bot token, encrypted at rest by n8n. |
| n8n → security controls | — | **No path exists.** |

## Unauthenticated webhook

**This is the most important item in this repository.**

The Webhook node has no authentication configured, and the workflow does not
verify Slack's request signature. Anyone who learns the URL can:

- submit arbitrary text for inference, consuming GPU indefinitely;
- cause the assistant to post arbitrary model output into your Slack channel,
  attributed to a bot named something like "Threat Intelligence";
- attempt prompt injection against the system prompts.

The webhook path is the only thing standing in the way, and a path is not a
credential — it appears in logs, browser history, and anywhere the URL is
pasted.

### Mitigations, in order of effectiveness

**1. Verify Slack signatures at a reverse proxy.** Slack signs every request
with `X-Slack-Signature` over `v0:{timestamp}:{body}` using your signing secret.
Verify it, and reject requests whose `X-Slack-Request-Timestamp` is more than
five minutes old, before anything reaches n8n. This is the real fix.

**2. Restrict by source.** Slack publishes its egress ranges. Allow only those
to reach the webhook path.

**3. n8n header authentication.** Configure the Webhook node with header auth —
but note Slack cannot send a custom header, so this only works if a proxy adds
it after verifying the request.

**4. Unguessable path.** Necessary, not sufficient. Do it anyway.

**5. Rate limit** per source at the proxy, to bound the damage of anything that
gets through.

## Data exposure

Security event text contains internal hostnames, usernames, private addressing,
file paths, and sometimes the live shape of an incident. It flows:

```
analyst → Slack (third-party SaaS) → n8n → Ollama → n8n → Slack
```

Two observations that follow:

**Slack already has the data.** The analyst pasted it there. This workflow does
not change that, but it does mean Slack's retention and access controls apply to
your incident telemetry — worth a conversation with whoever owns that decision.

**Ollama being self-hosted is the design.** Nothing leaves your network at the
inference step. Pointing `OLLAMA_BASE_URL` at a hosted API silently converts
this from a local-processing system into one that ships security telemetry to a
third party. Treat that value as a security control.

**n8n execution history retains everything.** Every pasted alert is stored in
the n8n database until pruned. See
[`observability.md`](observability.md#execution-history-is-sensitive).

## Credential handling

| Credential | Where | Exposure |
|---|---|---|
| Slack bot token | n8n credential store, encrypted with `N8N_ENCRYPTION_KEY` | Anyone with n8n editor access can use it, though not read it back |
| Slack signing secret | Your proxy — unused by this workflow | — |
| Ollama | None required | — |

Nothing in this repository contains a credential, credential ID, token, channel
ID or workspace identifier. Enforced by
[`../scripts/scan_sensitive_values.py`](../scripts/scan_sensitive_values.py) in
CI.

`includeLinkToWorkflow` is set to `false` on the Slack node. Leaving it on
appends your n8n instance URL to every message, publishing internal
infrastructure into a channel that may include guests or contractors.

## Prompt injection

Log content is attacker-influenceable. A username, User-Agent, filename or URL
in an alert can carry text intended to manipulate the model. It reaches the
model as a user message with no escaping or delimiting beyond the role boundary.

Realistic outcomes: a fabricated "benign" verdict, suppressed evidence, or
instructions echoed into the channel as if they were analysis.

What limits the damage here is architectural rather than technical: the model
cannot act. The worst case is a misleading Slack message reviewed by a human,
not an automated block on attacker-chosen infrastructure. Full analysis:
[`threat-model.md`](threat-model.md#t4--prompt-injection-via-log-content).

## What this system deliberately cannot do

- Block an IP, isolate a host, disable an account
- Close, suppress or escalate an alert
- Create or modify a case
- Read from any security system
- Take any action outside posting one Slack message

This is enforced by the absence of nodes, not by policy. Any future response
capability must be gated on analyst approval — see
[`human-in-the-loop.md`](human-in-the-loop.md).

## Residual risks

| Risk | Severity | Status |
|---|---|---|
| Unauthenticated webhook | High | Open — mitigate at the proxy |
| Prompt injection via log content | Medium | Open — bounded by no-action design |
| Model produces confident wrong assessment | Medium | Inherent — mitigated by human review |
| Execution history retains sensitive telemetry | Medium | Configuration-dependent |
| Silent drop of `ip`/`hash`/`linux` inputs | Medium | Open — roadmap item 1 |
| Inference failure produces silence | Low | Open — roadmap item 6 |
| GPU exhaustion from unbounded requests | Low | Open — rate limit at proxy |

Report a vulnerability: [`../SECURITY.md`](../SECURITY.md).
