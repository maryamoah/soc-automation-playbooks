# n8n workflows

Workflows built for [n8n](https://n8n.io), published as sanitized exports.

| Workflow | Status | Nodes | Trigger | Description |
|---|---|---|---|---|
| [ai-soc-assistant](ai-soc-assistant/) | **Implemented** | 14 | Webhook (Slack Events API) | Classifies a pasted security event, selects a source-specific analyst prompt, runs local LLM inference via Ollama, and replies in the Slack thread. |

## Importing

1. n8n → *Workflows* → *Import from File*.
2. Select the `*.sanitized.json` export.
3. Every export imports **inactive** with placeholder credentials. That is
   deliberate — see the workflow's `configuration.md` and `credentials.md`.
4. Replace placeholders, attach credentials, then activate.

Placeholders you will encounter across exports:

| Placeholder | Meaning |
|---|---|
| `OLLAMA_BASE_URL` | Base URL of your Ollama host, e.g. `http://10.x.x.x:11434` |
| `SLACK_BOT_USER_ID` | Your bot's Slack member ID (`U…`) |
| `SLACK_CREDENTIAL_ID` / `SLACK_API_CREDENTIAL` | Unresolvable credential reference — select a real one |

## Publishing a workflow here

n8n exports carry credential IDs, credential names, the instance ID and any
pinned execution data. Never commit a raw export.

```bash
python3 scripts/sanitize_n8n_export.py raw-export.json \
        workflows/n8n/<name>/<name>.sanitized.json --report
python3 scripts/validate_json.py
python3 scripts/scan_sensitive_values.py
```

The sanitizer exits non-zero if a known-bad pattern survives.

Before the first run, copy `scripts/sanitize-map.example.json` to
`scripts/sanitize-map.json` and fill in the literals specific to your
environment — internal addresses, bot IDs, hostnames, organisation-specific
paths. That file is git-ignored, because its **keys are the sensitive values
themselves**. Without a map the sanitizer still performs structural
sanitization and still refuses to exit cleanly if anything sensitive survives.

Each workflow directory must contain: `README.md`, the sanitized export,
`configuration.md`, `credentials.md`, `node-reference.md`, `testing.md`,
`troubleshooting.md`, and `CHANGELOG.md`. See
[`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

## Conventions

- **Document what runs, not what was intended.** If a branch is unwired or a
  field is misnamed, the documentation says so.
- **Never claim a planned integration is implemented.** Status columns are
  either `Implemented` or `Planned`, with no middle ground.
- **No response actions without an approval gate.** Nothing in this repository
  may block, isolate, disable or close on an LLM verdict alone. See
  [`../../docs/human-in-the-loop.md`](../../docs/human-in-the-loop.md).
