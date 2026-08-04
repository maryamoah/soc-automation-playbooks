# Contributing

Contributions are welcome — workflows, prompt improvements, documentation
corrections, and especially reports that a documented limitation is wrong.

## The rule that matters most

**Document what runs, not what was intended.**

If a branch is unwired, a field is misnamed, or an error path is missing, the
documentation says so. A repository that hides its defects is worse than one
that has them openly, because a reader cannot tell which kind they are looking
at.

Two corollaries:

- Never describe a planned integration as implemented. Status is `Implemented`
  or `Planned`, with nothing in between.
- Never commit a fabricated export to make a directory look complete.

## Before you start

Open an issue first for anything larger than a typo — a new workflow, a
classifier change, a prompt rewrite. It saves you building something that
conflicts with the roadmap.

## Contributing a workflow

Full procedure:
[`docs/workflow-lifecycle.md`](docs/workflow-lifecycle.md).

```bash
python3 scripts/sanitize_n8n_export.py raw.json \
        workflows/n8n/<name>/<name>.sanitized.json --report
python3 scripts/validate_json.py
python3 scripts/scan_sensitive_values.py
```

Copy `scripts/sanitize-map.example.json` to `scripts/sanitize-map.json` and add
your own hostnames, domains and project names **before** the first run. The
script cannot guess what is sensitive to you. That file is git-ignored — its
keys are the sensitive values.

Then confirm the sanitized file still imports into a clean n8n instance and runs
after credentials are reassigned. A sanitizer that breaks the workflow is worse
than no sanitizer.

Required files per workflow directory:

```
README.md              what it does, flow, supported inputs, status
<name>.sanitized.json
configuration.md       every value that must change, by node
credentials.md         credential setup and scopes
node-reference.md      node-by-node behaviour and data contract
testing.md             test cases and expected results
troubleshooting.md     symptoms, causes, fixes
CHANGELOG.md           version history including sanitization notes
```

## Contributing a prompt

Prompt edits are the highest-risk change in this repository. The prompts are
mostly *negative* constraints — "never conclude", "do not treat as proof" — and
tidying the wording is an easy way to delete a guard rail without noticing.

- Diff before and after and read what you removed.
- Re-run the full six-case test set in
  [`workflows/n8n/ai-soc-assistant/testing.md`](workflows/n8n/ai-soc-assistant/testing.md),
  especially cases 2 and 3, which exist to catch over-claiming.
- Preserve the shared discipline: verdict vocabulary, separation of severity
  from risk from confidence, detection metadata is not evidence, uncertainty
  resolves to `Requires Investigation`, plain text only, `Missing Information`
  required.
- State which model you tested with. Prompt behaviour is model-dependent.

## Contributing documentation

- Prose over bullet lists where an explanation is needed. Lists for genuine
  enumerations.
- Explain *why*, not only *what*. The reasoning is what survives a refactor.
- Relative links between files, so they work on GitHub and in a clone.
- No marketing tone. This is documentation for people who will be paged.

## Data rules

Never commit:

- Credentials, tokens, keys, signing secrets, credential IDs, instance IDs
- Slack channel, user, team or app IDs
- Production webhook URLs, tunnel URLs
- Internal domains, hostnames, RFC 1918 addressing
- Real security events or real IOCs from any environment
- Employer, university or customer names
- Execution history or pinned data

Examples must be synthetic and use RFC 5737 documentation addresses:
`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`.

## Before opening a pull request

```bash
python3 scripts/validate_json.py
python3 scripts/validate_examples.py
python3 scripts/scan_sensitive_values.py
```

All three must pass; CI runs them anyway. Then update the CHANGELOG, and check
that any status change is reflected in **both** the root README and the relevant
`workflows/<platform>/README.md` — that pair is the one contributors forget, and
it is what turns an honest repository into a misleading one.

## Commit messages

```
<type>(<scope>): <subject>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`.
Examples:

```
fix(ai-soc-assistant): wire linux Switch output to a prompt node
docs(threat-model): add prompt injection via enrichment responses
security(scripts): tighten internal-TLD detection to final label only
```

## Code of conduct

By participating you agree to the
[Code of Conduct](CODE_OF_CONDUCT.md).
