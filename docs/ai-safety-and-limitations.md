# AI safety and limitations

Read this before anyone treats the assistant's output as a verdict.

The assistant is an **analyst-assistance component**. It is not a security
authority, not a detection engine, and not a decision-maker. It reads one event
and produces a structured first pass. A human decides what happens next.

## The core limitation

**The model can be wrong, and wrong output looks exactly like correct output.**

There is no signal in a fluent, well-formatted, confidently-worded assessment
that distinguishes it from an accurate one. The `Confidence` field does not help
with this: it is the model's self-report, not a measured or calibrated quantity.
A model can state `Confidence: High` on a fabricated conclusion.

This is not a defect to be fixed by better prompting. It is the property of the
technology, and every other control in this document exists because of it.

## Specific failure modes

### Threat intelligence is supporting evidence, not proof

A reputation score describes an indicator's history elsewhere. It does not
establish what happened in your environment. Four of ninety-four engines
flagging an address is low-consensus and frequently a false positive on shared
hosting. Equally, a clean result is not evidence of benignity — it is evidence
of absence of reporting.

*(Enrichment is not implemented today. This applies to any intelligence an
analyst supplies manually, and to the planned enrichment stage.)*

### Blocked traffic is not a compromise

A firewall deny means the connection failed. Repeated denies mean it failed
repeatedly. Neither establishes reconnaissance, scanning, exploitation, malware,
command and control, or compromise.

This is the single most common analytic error in AI-generated triage, which is
why every firewall-facing prompt in this repository states it explicitly and why
the FortiGate example in [`../examples/outputs/`](../examples/outputs/) is built
around it: severity Medium, overall risk **Low**, because the traffic was
blocked.

### Private IPs and trusted services require context

RFC 1918 does not mean trusted — lateral movement is internal by definition. A
destination belonging to Microsoft, Google, Cloudflare or Akamai does not mean
benign; those platforms host attacker infrastructure alongside everything else.
Neither address class permits a conclusion on its own.

### MITRE ATT&CK mappings only where evidence supports them

A rule carrying a technique mapping is a statement **about the rule**, not about
what happened. `T1046` on a firewall-deny rule means the rule was written with
network service discovery in mind. It does not mean discovery occurred.

The prompts require that a technique appear in the report only when the
observable evidence independently supports it. The
[`ai-triage-result.schema.json`](../schemas/ai-triage-result.schema.json)
enforces the same discipline structurally: every MITRE entry requires a
`supporting_evidence` field, so an unsupported mapping cannot be expressed.

An empty MITRE array is the correct answer in most cases.

### Rule-ID-only input produces insufficient evidence

Detection metadata — rule ID, level, description, groups, fired-times, MITRE
mappings — explains why an alert fired. It is not evidence that anything
happened. Given only a rule ID, there is no observable fact against which any
explanation can be tested, and the correct output is a request for more data.

See [`../examples/outputs/insufficient-evidence.json`](../examples/outputs/insufficient-evidence.json).

### Severity, risk and confidence are three different things

- **Severity** — immediate operational impact of the observed event
- **Overall Risk** — likelihood it represents a genuine incident, after
  accounting for what actually happened
- **Confidence** — quality and completeness of the evidence

They routinely differ. Blocked malware on an endpoint: severity High (a control
failed), overall risk Medium (quarantined, no execution observed), confidence
High (the detection and action are directly observable).

None of the three is derived from the source rule's own level.

### Uncertainty is a valid answer

Every investigation prompt mandates `Requires Investigation` when the evidence
cannot distinguish between a benign and a malicious explanation. In the
normalized vocabulary this is `INSUFFICIENT_EVIDENCE`. It is a legitimate
outcome, not a failure — a guess presented as an assessment is worse than an
honest "not enough to say".

## Automated response

**Automated blocking must never rely on the LLM verdict alone.**

Nothing in this repository blocks anything. There is no node capable of it. Any
future response automation must:

1. gate on deterministic signals, not model text;
2. require explicit analyst approval for consequential actions;
3. be reversible, with the reversal documented before the action ships;
4. be logged with the evidence, the model output, and the approving human.

Consider the combination of T4 (prompt injection) and automated response: an
attacker who controls a log field could cause a block on infrastructure of their
choosing. Human approval is the control that breaks that chain.

## Verdict vocabulary

The deployed prompts emit natural-language verdicts. The normalized machine
vocabulary is defined in
[`../schemas/ai-triage-result.schema.json`](../schemas/ai-triage-result.schema.json)
for the planned parsing stage. They map as follows:

| Prompt output (implemented) | Normalized (planned) |
|---|---|
| `Malicious` | `TRUE_POSITIVE` |
| `False Positive` | `FALSE_POSITIVE` |
| `Suspicious` | `SUSPICIOUS` |
| `Benign` | `INFORMATIONAL` |
| `Requires Investigation` | `INSUFFICIENT_EVIDENCE` |

Confidence uses `LOW` / `MEDIUM` / `HIGH` in both.

`Benign` → `INFORMATIONAL` is the one mapping worth pausing on. The prompts
reserve `Benign` for activity confirmed as legitimate — not merely unconfirmed
as malicious. Where legitimacy is assumed rather than established, the correct
verdict is `Requires Investigation`.

## What analysts should be told

If you deploy this, say these things out loud to the people using it:

1. It is a first pass, not an answer.
2. It can be confidently wrong. Confidence is self-reported.
3. It sees one event, with no history and no environmental context.
4. Silence may mean it failed, not that nothing was found.
5. Its output can be manipulated by content in the log itself.
6. Never close an alert on its say-so. Verify against the source system.
7. If it contradicts your judgement, your judgement is the one with context.

Point 7 matters most. The purpose of the tool is to save reading time, not to
replace an analyst's assessment of their own environment.

## Measuring whether it helps

Consider sampling outputs against analyst ground truth on a regular cadence,
tracking: verdict agreement, over-claiming rate (blocked traffic described as
compromise), unsupported MITRE mappings, and format compliance. Without
measurement you cannot tell whether a model upgrade improved things or quietly
degraded them.
