# Roadmap

Everything here is **planned**. Nothing in this document is implemented. Items
are ordered by a rough ratio of harm-reduced to effort.

Status values used across the repository: `Planned`, `In progress`,
`Implemented`. There is no intermediate state — a workflow that partly works is
`Planned` until the export exists and the documentation matches it.

---

## 1. Wire the `ip`, `hash` and `linux` routes

**Status:** Planned · **Priority:** High

Switch outputs 0, 1 and 4 connect to nothing. Items routed there end a
*successful* execution with no reply and no error. Wazuh alerts whose rule
groups include `linux` land here, so SSH brute-force alerts currently disappear
silently.

**Acceptance criteria**
- A fallback output on `Route Investigation` so no input can be silently dropped.
- Dedicated prompt nodes for IOC (`ip`, `hash`) and Linux/auth events.
- Test cases 5 and 6 in `testing.md` updated from "no reply" to a real
  expectation.
- Limitations sections updated in the root README, workflow README,
  `architecture.md`, `threat-model.md` (T6) and `observability.md`.

---

## 2. Parse and validate the model response

**Status:** Planned · **Priority:** High

`Compiler` takes `message.content` as an opaque string. Nothing checks that the
model followed the required format; malformed output reaches the analyst
verbatim.

**Acceptance criteria**
- Parse the plain-text report into the structure defined by
  [`../schemas/ai-triage-result.schema.json`](../schemas/ai-triage-result.schema.json).
- Validate against the schema before delivery.
- Map natural-language verdicts to the normalized vocabulary per
  [`ai-safety-and-limitations.md`](ai-safety-and-limitations.md#verdict-vocabulary).
- On validation failure, deliver a clear "could not parse" message rather than
  raw output.
- Strip reasoning blocks (`<think>…</think>`) if present.

This is a prerequisite for items 3 and 4.

---

## 3. Deterministic risk score

**Status:** Planned · **Priority:** High

There is currently no risk-scoring formula anywhere in the workflow. All four
assessment fields are model-generated text.

**Acceptance criteria**
- A score computed in a Code node from observable facts only — action taken
  (deny/allow/block/quarantine), whether execution was observed, asset
  criticality, and enrichment once item 4 exists.
- Computed **independently** of the model verdict, and displayed alongside it so
  disagreement is visible rather than hidden.
- The formula documented explicitly, with worked examples.
- Never used as a sole trigger for any action.

The point is not a better number. It is having one signal in the system that a
language model cannot talk its way past.

---

## 4. Threat-intelligence enrichment

**Status:** Planned · **Priority:** Medium

VirusTotal and AbuseIPDB lookups for extracted indicators, normalized to
[`../schemas/enrichment-result.schema.json`](../schemas/enrichment-result.schema.json)
and supplied to the model as evidence.

**Acceptance criteria**
- Indicator extraction as a discrete stage.
- Private, reserved and documentation addresses skipped — never sent to a third
  party. This is a data-leakage control, not an optimisation.
- Caching to respect rate limits and control cost.
- Results presented to the model as *supporting evidence*, with caveats
  attached, never as proof.
- Absence of intelligence explicitly reported as absence, not benignity.
- Failure of a lookup must not fail the analysis.

---

## 5. Slack request signature verification

**Status:** Planned · **Priority:** High (security)

The webhook is unauthenticated. See
[`threat-model.md`](threat-model.md#t1--unauthorised-webhook-use).

**Acceptance criteria**
- `X-Slack-Signature` verified against the signing secret.
- `X-Slack-Request-Timestamp` older than five minutes rejected (replay).
- Invalid requests rejected before any inference is triggered.
- The `url_verification` challenge answered properly, removing the temporary
  workaround in `credentials.md`.
- Reference proxy configuration published.

---

## 6. Error handling on the inference call

**Status:** Planned · **Priority:** Medium

No timeout, no retry, no error branch. Failure produces silence.

**Acceptance criteria**
- Explicit timeout sized to the largest prompt.
- Retry with backoff on transient failure.
- Error output wired to a Slack reply in the analyst's own thread.
- Error workflow notifying a maintenance channel.

---

## 7. Alert aggregation

**Status:** Planned · **Priority:** Medium

Every message is analysed alone. Ten related alerts produce ten unrelated
analyses, and the system cannot see a campaign.

**Acceptance criteria**
- Correlation window grouping related alerts by source, destination, user or
  host.
- Aggregated evidence presented to the model as one investigation.
- Deduplication of repeated identical alerts.
- Requires persistence, which this workflow currently has none of.

---

## 8. Wazuh → TheHive → Cortex playbook

**Status:** Not built · design note:
[wazuh-thehive-cortex.md](../workflows/shuffle/planned/wazuh-thehive-cortex.md)

This would require adopting Shuffle, which this project has not done — no
Shuffle instance is deployed and no Shuffle workflow exists. Adding a second
automation platform is a decision in its own right, not just a workflow to
build.

---

## 9. TheHive case creation with an approval gate

**Status:** Planned · **Priority:** Low

Case creation is the first write action into security infrastructure and must
land behind an explicit approval gate meeting every requirement in
[`human-in-the-loop.md`](human-in-the-loop.md#requirements-for-future-response-automation).

---

## 10. OpenCTI correlation

**Status:** Planned · **Priority:** Low

Correlate indicators against internal threat intelligence for campaign and actor
context.

---

## Explicitly not planned

| Not planned | Why |
|---|---|
| Automated blocking on model verdict | Combined with prompt injection, this lets an attacker choose what your firewall blocks. |
| Automated alert closure | Removes the human from the only decision that matters. |
| Autonomous multi-step response | Not appropriate for a component whose confidence is self-reported. |
| Fabricated Shuffle exports to fill the directory | Shuffle was never used here. Misrepresents the project. |

## Contributing

Pick an item, open an issue referencing it, and read
[`../CONTRIBUTING.md`](../CONTRIBUTING.md). Items 1, 5 and 6 are the most useful
to a deployment and the least dependent on anything else.
