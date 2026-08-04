# Examples

All data here is **synthetic**. Every address is from an RFC 5737 documentation
range (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`). No file contains a
real security event, a real indicator, or any identifier from a real
environment.

## What is produced by the current workflow, and what is not

This distinction matters — the directory contains both real output formats and
design targets.

| Path | Produced by the implemented workflow? |
|---|---|
| `inputs/*.json` | **Yes** — real input format. Post these to the webhook. |
| `outputs/slack-triage-message.txt` | **Yes** — real output format (plain text, in-thread). |
| `outputs/*.json` | **No** — the workflow emits no JSON. Planned structure for the parsing stage. |
| `enrichment/*.json` | **No** — the workflow performs no enrichment. Reference payloads for the planned stage. |

## `inputs/`

Slack Events API payloads, shaped exactly as the Webhook node receives them —
the event nested under `body`, which is what makes them usable directly:

```bash
curl -X POST "$N8N_TEST_URL" -H 'Content-Type: application/json' \
     -d @examples/inputs/wazuh-windows-alert.json
```

| File | Expected `input_type` | Purpose |
|---|---|---|
| `wazuh-firewall-alert.json` | `fortigate` | Denied SNMP traffic. Tests that blocked traffic is not reported as compromise. |
| `wazuh-windows-alert.json` | `windows` | Kerberos 4768, result `0x6`, computer account. Tests that a Kerberoasting rule mapping is not treated as evidence of Kerberoasting. |
| `wazuh-rule-id-only-alert.json` | `wazuh_json` | Detection metadata with no event body. Tests that no verdict is asserted from a rule ID. |
| `slack-event.json` | `general` | A plain question. Tests the conversational path. |

To test the dead-end routes, paste a bare IP (`192.0.2.10`) or a bare hash. Both
should produce **no reply at all** — see
[`../workflows/n8n/ai-soc-assistant/testing.md`](../workflows/n8n/ai-soc-assistant/testing.md).

## `enrichment/`

**Planned — not implemented.** No node in the shipped workflow calls VirusTotal
or AbuseIPDB.

Each file contains three parts: `_meta` (status and provenance),
`raw_provider_response` (synthetic, provider-shaped), and `normalized` (conforms
to [`../schemas/enrichment-result.schema.json`](../schemas/enrichment-result.schema.json)
and is what `validate_examples.py` checks).

Note the `caveats` arrays. They are part of the contract, not commentary: a
reputation score delivered without its qualifications invites exactly the
over-trust the rest of this repository argues against.

## `outputs/`

`slack-triage-message.txt` is the real thing — plain text, `•` bullets, no
Markdown, sections separated by blank lines. Its reviewer notes explain why the
MITRE mapping present on the source rule does *not* appear in the report, and
why severity and overall risk differ.

The four `.json` files conform to
[`../schemas/ai-triage-result.schema.json`](../schemas/ai-triage-result.schema.json)
and demonstrate the normalized verdict vocabulary:

| File | Verdict | Point of the example |
|---|---|---|
| `informational-triage.json` | `INFORMATIONAL` | Routine computer-account logon. Nothing to do. |
| `suspicious-triage.json` | `SUSPICIOUS` | Severity Medium, **overall risk Low** — the traffic was blocked. |
| `malicious-triage.json` | `TRUE_POSITIVE` | Severity High, **overall risk Medium** — malware quarantined, no execution observed. Carries the only MITRE mapping in the set, with required supporting evidence. |
| `insufficient-evidence.json` | `INSUFFICIENT_EVIDENCE` | Rule ID only. A legitimate answer, not a failure. |

## Validation

```bash
python3 scripts/validate_examples.py
```

Runs in CI. Inputs are checked as Slack envelopes, and their embedded alerts
against the Wazuh schema; enrichment `normalized` blocks and all triage outputs
against their schemas.

## Adding an example

Synthetic only, documentation addresses only, and add it to `VALIDATION_MAP` or
`SLACK_INPUTS` in `scripts/validate_examples.py` so it is actually checked. An
unvalidated example drifts out of sync with its schema and then misleads
somebody.
