# Workflow lifecycle

How a workflow gets from a local n8n instance into this repository, and how it
changes afterwards.

## States

| State | Meaning | In repo |
|---|---|---|
| **Draft** | Being built locally. Contains real credentials and real data. | Never |
| **Implemented** | Working, sanitized, exported, documented. | Yes |
| **Planned** | Designed and documented. No export exists. | Design docs only |
| **Deprecated** | Superseded. Retained for reference with a notice. | Yes, marked |

There is no state between Planned and Implemented. A workflow that partly works
is Planned until the export exists and the documentation matches it.

## Publishing a workflow

### 1. Export

n8n → workflow → *Download*. The raw export contains credential IDs, credential
names, the instance ID, the workflow and version IDs, and any pinned execution
data. Do not commit it.

### 2. Sanitize

```bash
python3 scripts/sanitize_n8n_export.py raw.json \
        workflows/n8n/<name>/<name>.sanitized.json --report
```

Create your replacement map first: copy `scripts/sanitize-map.example.json` to
`scripts/sanitize-map.json` and add anything specific to your environment —
hostnames, internal domains, project codenames, real IPs embedded in prompt
examples. The script cannot guess what is sensitive to you.

`sanitize-map.json` is git-ignored and must stay that way. Its keys are the
sensitive literals, so committing it would publish them.

The `--report` flag prints what was removed and replaced. Read it. It is also
the source for the workflow CHANGELOG's Security section.

### 3. Verify

```bash
python3 scripts/validate_json.py
python3 scripts/scan_sensitive_values.py
python3 scripts/validate_examples.py
```

Then read the sanitized file yourself. Search for your own domain, your
employer's name, and any hostname convention you use. Automated scanning finds
patterns; only you know your naming.

### 4. Confirm it still imports

Import the sanitized file into a clean n8n instance. It should import inactive,
with an unresolvable credential, and every node present. Reassign the credential,
replace the placeholders, and run one test event. If it does not run after that,
the sanitizer broke something.

### 5. Document

Each workflow directory requires:

```
README.md            what it does, flow, supported inputs, status
<name>.sanitized.json
configuration.md     every value that must change, by node
credentials.md       credential setup and scopes
node-reference.md    node-by-node behaviour and data contract
testing.md           test cases and expected results
troubleshooting.md   symptoms, causes, fixes
CHANGELOG.md         version history including sanitization notes
```

**Document what runs, not what was intended.** If a branch is unwired, a field
is misnamed, or an error path is missing, the documentation says so. A
repository that hides its defects is worse than one that has none, because
readers cannot tell which kind they are looking at.

### 6. Add examples

Synthetic only. RFC 5737 addresses. Never a real event from your environment,
even one you consider harmless — real events carry real hostnames, real
usernames and real timing.

## Changing a published workflow

| Change | Version | Required |
|---|---|---|
| Prompt wording | Patch | Re-run the full test set |
| New classifier route | Minor | New test case; update README and node-reference |
| Wiring a dead-end output | Minor | Update the limitations sections everywhere they appear |
| Node added or removed | Minor | Update node-reference and diagrams |
| Data contract change | **Major** | Update schemas and examples |
| Credential type change | **Major** | Update credentials.md |

Prompt edits deserve the most caution. These prompts are largely negative
constraints, and tidying the wording is an easy way to delete a guard rail
without noticing. Diff before and after, and specifically re-run the cases that
exist to catch over-claiming.

## Deprecating

Do not delete. Mark the workflow README with a deprecation notice stating what
replaces it and why, move it under `workflows/n8n/deprecated/`, and record it in
the repository CHANGELOG. Someone is running the old version.

## Promoting a Planned workflow

1. Build it.
2. Export and sanitize.
3. Write the full documentation set.
4. Replace the design document with a pointer to the implemented workflow.
5. Update the status tables in the root README **and** in
   `workflows/<platform>/README.md`.
6. Update [`roadmap.md`](roadmap.md).

Step 5 is the one that gets missed, and it is the one that turns an honest
repository into a misleading one.
