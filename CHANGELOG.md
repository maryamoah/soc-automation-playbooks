# Changelog

Notable changes to this repository. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Workflow-specific history lives with each workflow, e.g.
[`workflows/n8n/ai-soc-assistant/CHANGELOG.md`](workflows/n8n/ai-soc-assistant/CHANGELOG.md).

## [1.0.0] — 2026-08-03

Initial public release.

### Added
- **AI SOC Assistant** (n8n, implemented): sanitized 14-node export plus full
  documentation — README, configuration, credentials, node reference, testing,
  troubleshooting, changelog.
- Documentation set covering architecture, getting started, deployment, workflow
  lifecycle, security model, threat model, data flow, human-in-the-loop
  controls, AI safety and limitations, secrets management, observability,
  testing strategy, FAQ and roadmap.
- JSON Schemas for Wazuh alerts, the normalized event contract, enrichment
  results (planned) and normalized triage results (planned).
- Synthetic examples: four Slack-shaped inputs, two enrichment reference
  payloads, four normalized triage outputs, one real-format Slack message.
- Validation tooling: `validate_json.py`, `validate_examples.py`,
  `scan_sensitive_values.py`, `sanitize_n8n_export.py` — all dependency-free.
- Mermaid diagrams: architecture, data flow, decision flow, workflow stages,
  rendered inline in `diagrams/README.md` (GitHub does not render bare `.mmd`).
- `SETUP.md`: placeholder replacement, first push, and repository settings for
  anyone publishing their own copy.
- GitHub Actions: JSON validation, Markdown lint, secret scan, Python
  validation. Issue templates, PR template, CODEOWNERS, Dependabot.
- Three forward-looking SOAR design notes under `workflows/shuffle/planned/`,
  labelled `Not built`. Shuffle was not used in this project and no Shuffle
  instance is deployed.

### Security
- All credential IDs, credential names, instance IDs, workflow IDs, version IDs
  and pinned execution data removed from the published export.
- Internal RFC 1918 addressing replaced with RFC 5737 documentation addresses.
- A real public IPv4 address in a prompt example replaced.
- Slack bot user ID and organisation-specific webhook path genericized.
- Export forced to `active: false`.
- Secret scanning enforced in CI.
- The sanitizer's replacement map is loaded from a git-ignored file rather than
  hard-coded, so the tool cannot republish the literals it removes.

### Known limitations
Documented in [`README.md`](README.md#known-limitations). Summary: no
threat-intelligence enrichment, no deterministic risk score, no parsing of the
model response, three unconnected classifier routes that drop input silently, no
alert aggregation, no retry or error branch, no Slack signature verification,
and no rate limiting.

[1.0.0]: https://github.com/maryamoah/soc-automation-playbooks/releases/tag/v1.0.0
