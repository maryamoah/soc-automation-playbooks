# Security policy

## Reporting a vulnerability

Do not open a public issue for a security vulnerability.

Report privately through **GitHub Security Advisories** (*Security* → *Report a
vulnerability*), or by email to the address in
[`.github/CODEOWNERS`](.github/CODEOWNERS).

Please include: what the issue is, how to reproduce it, what an attacker gains,
and which files or workflows are affected.

Expect acknowledgement within a few days and an assessment within two weeks.
This is a community project, not a vendor with an on-call rota — timelines are
best effort.

## If you find a secret in this repository

Treat it as urgent. Report it privately and immediately.

Anything committed here should be assumed compromised the moment it was pushed —
rotation resolves the exposure, history rewriting does not. See
[`docs/secrets-management.md`](docs/secrets-management.md#if-a-secret-is-committed).

## Scope

**In scope**
- Secrets, credentials, internal hostnames, private addressing or real security
  events present in this repository
- Vulnerabilities in the workflow design itself
- Flaws in the sanitization or scanning scripts that could allow a secret to be
  published
- Documentation that materially understates a risk

**Out of scope**
- Vulnerabilities in n8n, Slack or Ollama — report those upstream
- Your own deployment's configuration
- The known limitations documented in [`README.md`](README.md#known-limitations)
  and [`docs/threat-model.md`](docs/threat-model.md). These are disclosed, not
  hidden. If you can show one is materially worse than described, that is a
  valid report.

## Known and accepted risks

Documented in full in [`docs/threat-model.md`](docs/threat-model.md). The two
that matter most:

**The webhook is unauthenticated.** The n8n Webhook node has no auth configured
and the workflow does not verify Slack's request signature. Anyone with the URL
can drive your LLM and cause arbitrary model output to be posted into a security
channel. Mitigate with a verifying reverse proxy, source restrictions and rate
limiting. Roadmap item 5.

**Model output can be wrong or manipulated.** Assessments are advisory. The
model has no tools and cannot act, which bounds the damage to a misleading
message reviewed by a human. See
[`docs/ai-safety-and-limitations.md`](docs/ai-safety-and-limitations.md).

## Publishing safely

If you contribute a workflow:

1. Sanitize with `scripts/sanitize_n8n_export.py`, extending its replacement map
   with your own hostnames and project names first.
2. Run `scripts/scan_sensitive_values.py`.
3. Read the sanitized file yourself. Search for your domain, your employer's
   name and your hostname conventions. Automated scanning finds patterns; only
   you know your naming.
4. Use RFC 5737 documentation addresses in examples: `192.0.2.0/24`,
   `198.51.100.0/24`, `203.0.113.0/24`.
5. Never commit a real security event from your environment.

Screenshots are a common leak vector — workspace names, channel names, internal
hostnames, colleagues' names, real alert content. See
[`assets/screenshots/README.md`](assets/screenshots/README.md).

## Safe harbour

Good-faith research on this repository is welcome and will not be pursued.
Please do not test against infrastructure you do not own.
