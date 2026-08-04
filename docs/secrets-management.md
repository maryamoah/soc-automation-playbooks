# Secrets management

## What is a secret here

| Value | Sensitivity | Where it lives |
|---|---|---|
| Slack bot token (`xoxb-…`) | High | n8n credential store |
| Slack signing secret | High | Reverse proxy — **not used by this workflow** |
| `N8N_ENCRYPTION_KEY` | Critical | n8n host environment |
| Webhook URL | Medium — it is the only access control today | n8n, Slack app config |
| `OLLAMA_BASE_URL` | Low value, high impact | n8n node parameter |
| Internal hostnames and addressing | Medium | Should not appear in this repository at all |

The webhook URL entry is unusual and deliberate. Because the webhook is
unauthenticated, the path *is* the credential — handle it accordingly, and
understand that this is a weak position to be in. See
[`security-model.md`](security-model.md#unauthenticated-webhook).

## What must never be committed

- API keys, tokens, passwords, signing secrets, private keys
- n8n credential IDs or credential names
- n8n instance IDs
- Slack channel, user, team or app IDs
- Production webhook URLs, ngrok or other tunnel URLs
- Internal domains, hostnames, RFC 1918 addresses
- Real security events, real IOCs from your environment
- Employer, university or customer names
- Execution history or pinned data

Use RFC 5737 documentation addresses in examples: `192.0.2.0/24`,
`198.51.100.0/24`, `203.0.113.0/24`.

## Enforcement

Three layers, in order of reliability:

**1. Sanitize at export.**
[`../scripts/sanitize_n8n_export.py`](../scripts/sanitize_n8n_export.py) strips
credential IDs and names, the instance ID, the workflow and version IDs, and
pinned data; forces `active: false`; applies a literal replacement map; and
re-scans its own output, exiting non-zero if anything survives.

```bash
python3 scripts/sanitize_n8n_export.py raw.json clean.json --report
```

Before first use, copy `scripts/sanitize-map.example.json` to
`scripts/sanitize-map.json` and fill in your own literals. That file is
git-ignored by design: its keys are the sensitive values, so committing it would
republish exactly what the sanitizer exists to remove. A scanner only catches
what someone anticipated.

**2. Scan the whole repository.**
[`../scripts/scan_sensitive_values.py`](../scripts/scan_sensitive_values.py)
looks for tokens, keys, JWTs, private keys, tunnel URLs, hard-coded password
assignments, internal TLDs, n8n credential and instance IDs, and non-documentation
IP addresses.

**3. Run it in CI.**
[`../.github/workflows/secret-scan.yml`](../.github/workflows/secret-scan.yml)
runs on every push and pull request.

A local pre-commit hook is worth the two lines:

```bash
cat > .git/hooks/pre-commit <<'HOOK'
#!/bin/sh
python3 scripts/scan_sensitive_values.py || {
  echo "Sensitive values detected. Commit aborted."; exit 1; }
HOOK
chmod +x .git/hooks/pre-commit
```

## Screenshots are a leak vector

Screenshots of an n8n canvas or a Slack thread routinely contain more than
intended: workspace names, channel names, internal hostnames, private
addressing, real alert content, node URLs shown under a node, and colleagues'
names and avatars.

Before adding any image to [`../assets/screenshots/`](../assets/screenshots/),
read the redaction checklist in that directory's README. Redact by painting over
at full opacity — blur and pixelation are frequently reversible.

## Runtime secret handling

**n8n credential store.** Credentials are encrypted at rest with
`N8N_ENCRYPTION_KEY`. Set it explicitly and back it up separately from the
database; losing it means recreating every credential by hand.

**Environment variables in nodes.** n8n blocks `$env` access inside nodes by
default (`N8N_BLOCK_ENV_ACCESS_IN_NODE=true`). Leave it enabled on any
multi-user instance: disabling it makes every environment variable — including
the encryption key and database credentials — readable from any Code node, which
is a privilege escalation path.

This is why the shipped export uses literal placeholders rather than `$env`
expressions. A broken placeholder fails loudly; an `$env` reference on a blocked
instance fails quietly.

**Rotation.** Rotate the Slack token on any suspected exposure — a screenshot, a
log, a chat message, a repository. Reinstalling the Slack app issues a new bot
token. Rotate the signing secret from the app's Basic Information page.

## If a secret is committed

1. Rotate it immediately. Assume it is compromised the moment it is pushed.
2. Then clean history (`git filter-repo` or BFG) and force-push.

In that order. Rewriting history does not un-publish anything that was already
cloned, mirrored or indexed — rotation is what actually resolves the exposure.
