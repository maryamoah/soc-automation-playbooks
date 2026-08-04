# Testing strategy

Three layers. The first two are automated and cheap; the third is manual and is
the only one that tests whether the system is actually useful.

## Layer 1 — Repository validation (CI)

Runs on every push and pull request. No n8n, no Ollama, no network.

| Script | Checks |
|---|---|
| [`validate_json.py`](../scripts/validate_json.py) | Every `.json` parses. Schemas look like schemas. n8n exports have valid structure, unique node names, and no connection pointing at a non-existent node. Sanitized exports are inactive and free of instance IDs and pinned data. |
| [`validate_examples.py`](../scripts/validate_examples.py) | Examples conform to the schemas. Uses `jsonschema` when installed, otherwise a bundled subset validator so a fresh clone works with no install step. |
| [`scan_sensitive_values.py`](../scripts/scan_sensitive_values.py) | Tokens, keys, JWTs, private keys, tunnel URLs, hard-coded passwords, internal TLDs, n8n credential and instance IDs, non-documentation IP addresses. |

```bash
python3 scripts/validate_json.py
python3 scripts/validate_examples.py
python3 scripts/scan_sensitive_values.py
```

These validate the **repository**, not a deployment. Passing means the export is
well-formed and sanitized — not that your Ollama host is up.

## Layer 2 — Workflow behaviour

Requires a running n8n. Full procedure:
[`../workflows/n8n/ai-soc-assistant/testing.md`](../workflows/n8n/ai-soc-assistant/testing.md).

Six cases. The assertion that matters is `input_type` on the Classifier output —
check it before judging the model's answer, because a good answer from the wrong
prompt is luck.

| # | Input | Expect |
|---|---|---|
| 1 | Windows Kerberos 4768 alert | `windows`, no credential-theft claim |
| 2 | FortiGate deny | `fortigate`, blocked ≠ compromised, overall risk Low |
| 3 | Rule ID only | `wazuh_json`, insufficient evidence, no verdict asserted |
| 4 | Free-text question | `general`, conversational, no verdict block |
| 5 | Bare IP | `ip` — **no reply** (known dead end) |
| 6 | Bare hash | `hash` — **no reply** (known dead end) |

Cases 5 and 6 assert a **defect**, deliberately. When the routes are wired, the
expectations change and this table changes with them. A test suite that only
asserts intended behaviour will not tell you when a known gap silently becomes a
different gap.

Plus three loop-guard cases: `bot_id` present, `subtype: bot_message`, and the
configured bot user ID. All three must produce zero items from the Classifier.

## Layer 3 — Output quality

The layer that determines whether the system helps or harms, and the one that
cannot be automated.

For each investigation response, check:

- **Blocked ≠ breached.** No claim of successful access from a deny.
- **Metadata is not evidence.** Rule name, level, fired-times and MITRE mappings
  explain why the alert fired, not what happened.
- **MITRE only where evidence supports it.** Traceable to an observable.
- **No assumption from address class.** Private is not trusted; a big-name
  destination is not benign.
- **Uncertainty resolves to `Requires Investigation`.**
- **`Missing Information` populated** with things that would change the verdict.
- **Evidence contains only observable facts.**
- **Plain text**, no Markdown.

A response that is beautifully formatted and analytically wrong is worse than a
messy correct one, because it is more persuasive. Weight review accordingly.

### Sampling

Sample regularly against analyst ground truth and track verdict agreement,
over-claiming rate, unsupported MITRE mappings, and format compliance. This is
the only way to detect that a model upgrade degraded analysis.

## When to re-test

| Change | Layer 1 | Layer 2 | Layer 3 |
|---|---|---|---|
| Documentation | Yes | — | — |
| Example or schema | Yes | — | — |
| Prompt edit | Yes | Yes | **Yes — priority** |
| Classifier edit | Yes | **Yes — all six** | Spot check |
| Model change | — | Yes | **Yes — full** |
| n8n upgrade | Yes | Yes | Spot check |
| Wiring a dead-end route | Yes | Yes, update cases 5–6 | Yes |

## Gaps

Stated so nobody assumes coverage that does not exist:

- **No automated end-to-end test.** Layer 2 is entirely manual.
- **No Code node unit tests.** The classifier is the highest-risk component and
  has no test harness. Extracting it to a testable module is worthwhile.
- **No load testing.** Concurrency behaviour is unmeasured.
- **No prompt-injection test cases.** T4 is documented but not tested.
- **No regression corpus.** There is no stored set of events with known-correct
  assessments to diff a model change against. This is the most valuable thing
  missing.
