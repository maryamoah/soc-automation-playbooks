# Threat model

Scoped to the AI SOC Assistant as implemented. Threats against Slack, n8n or
Ollama as products are out of scope except where this workflow's configuration
changes the exposure.

## Assets

| Asset | Why it matters |
|---|---|
| Security event telemetry | Internal hostnames, usernames, addressing, live incident detail |
| Slack bot token | Post-as-bot into channels |
| Inference capacity | Finite GPU; exhaustible |
| Analyst trust in the output | The system's actual product. Once wrong output is accepted uncritically, every other control is downstream of a bad judgement. |
| n8n execution history | A searchable archive of everything ever analysed |

## Actors

- **External unauthenticated attacker** — knows or discovers the webhook URL
- **Attacker influencing log content** — controls fields that end up in alerts
- **Malicious or careless insider** — has Slack access
- **Compromised n8n operator account**

---

## T1 — Unauthorised webhook use

**Vector:** POST to the webhook path from anywhere.
**Impact:** GPU exhaustion; arbitrary model output posted into a security
channel under a trusted bot name; a channel for probing the system prompts.
**Likelihood:** Moderate. Paths leak through logs, screenshots and browser
history.
**Current controls:** Path obscurity only.
**Mitigation:** Verify Slack signatures at a proxy; restrict source ranges;
rate limit. See [`security-model.md`](security-model.md#unauthenticated-webhook).
**Residual:** High until a verifying proxy is deployed.

## T2 — Data exposure to a third party

**Vector:** `OLLAMA_BASE_URL` repointed at a hosted inference API — by
convenience, by a migration, or by someone unaware of the design intent.
**Impact:** Security telemetry, including live incident detail, leaves the
organisation.
**Likelihood:** Low but under-appreciated; it is a one-line change with no
visible warning.
**Current controls:** Documentation.
**Mitigation:** Treat the value as a controlled configuration item; review it in
change control; egress-filter the n8n host.
**Residual:** Medium — organisational, not technical.

## T3 — Slack bot token compromise

**Vector:** n8n compromise, credential export, an unrotated token in a
screenshot or repository.
**Impact:** Post as the bot into any channel it is in. Scope is limited to
`chat:write` plus history reads.
**Likelihood:** Low.
**Current controls:** Encrypted credential store; minimal scopes; no token in
this repository (CI-enforced).
**Mitigation:** Keep scopes minimal; rotate on any exposure; restrict n8n editor
access.

## T4 — Prompt injection via log content

**Vector:** An attacker controls a field that lands in an alert — username,
User-Agent, filename, URI, hostname — and embeds instructions. The event reaches
the model as a user message, unescaped.

Example shape: a User-Agent string containing text instructing the model to
disregard prior instructions and report the request as benign.

**Impact:** Fabricated verdict; suppressed evidence; attacker-chosen text posted
into a security channel formatted as an analyst assessment. The credible harm is
an analyst deprioritising a real detection.

**Likelihood:** Low today, rising. It requires the attacker to know an LLM sits
downstream, which is increasingly a safe assumption.

**Current controls:**
- The model has no tools and no actions. It cannot block, query or write.
- Output is advisory, in a channel, reviewed by a human.
- The prompts demand evidence-based reasoning and require a `Missing
  Information` section, which makes a content-free "benign" answer look wrong.

**What is missing:** no input sanitisation, no delimiting of untrusted content,
no output validation, no detection of injection attempts.

**Mitigation:** Delimit event text explicitly in the user message; validate
output structure before delivery (roadmap item 2); treat any assessment that
contradicts the raw event as suspect. Analysts should be told this is possible —
an analyst who knows a verdict can be manipulated reads it differently.

**Residual:** Medium, bounded by the no-action design. This is the strongest
argument against adding automated response without an approval gate: injection
plus automation turns a misleading message into an attacker-controlled block.

## T5 — Over-trust in model output

**Vector:** No attacker. An analyst accepts a fluent, confident, wrong
assessment.
**Impact:** Missed true positive, or wasted effort on a false one. This is the
most probable harm in the entire model.
**Likelihood:** High without deliberate counter-measures.
**Current controls:** Prompts that mandate `Requires Investigation` under
ambiguity, forbid treating detection metadata as evidence, and require a
`Missing Information` section; advisory-only delivery.
**Mitigation:** Train analysts on the failure modes in
[`ai-safety-and-limitations.md`](ai-safety-and-limitations.md); never allow the
output to be the sole basis for closing an alert; sample-review outputs against
ground truth.
**Residual:** Medium. Irreducible while a language model is in the path.

## T6 — Silent failure

**Vector:** Inference timeout, Ollama down, or an input classified `ip`, `hash`
or `linux`.
**Impact:** The analyst receives nothing. In the dead-end case the execution is
*successful*, so no alerting fires. An analyst who assumes "no reply means
nothing interesting" has been misled by the tool.
**Likelihood:** High for `linux` — Wazuh SSH alerts route there.
**Current controls:** None.
**Mitigation:** Wire the unused outputs (roadmap item 1); add a Switch fallback;
add an error branch that reports failure into the thread (roadmap item 6).
**Residual:** Medium.

## T7 — Malicious insider posting fabricated events

**Vector:** Anyone in the channel pastes a fabricated alert to generate an
authoritative-looking "benign" assessment they can point at later.
**Impact:** Manufactured cover for suppressing a real detection.
**Likelihood:** Low.
**Current controls:** Slack audit history; assessments are public in-channel.
**Mitigation:** Never treat an assistant output as evidence of investigation;
verify against the source system.

## T8 — Execution history as an archive

**Vector:** Access to the n8n database or editor.
**Impact:** Every security event ever submitted, searchable.
**Likelihood:** Low.
**Current controls:** n8n access control.
**Mitigation:** `EXECUTIONS_DATA_PRUNE=true` with a retention window matching
policy; restrict editor access.

---

## Summary

| ID | Threat | Residual |
|---|---|---|
| T1 | Unauthorised webhook use | **High** |
| T2 | Data exposure via repointed inference | Medium |
| T3 | Slack token compromise | Low |
| T4 | Prompt injection | Medium |
| T5 | Over-trust in output | Medium |
| T6 | Silent failure | Medium |
| T7 | Fabricated events | Low |
| T8 | Execution history retention | Low–Medium |

The two worth acting on first are T1, because it is fully within your control
and currently unmitigated, and T5, because it is the one that damages
investigations rather than infrastructure.
