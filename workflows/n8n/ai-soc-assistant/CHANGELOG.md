# Changelog — AI SOC Assistant

All notable changes to this workflow. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Version numbers describe the **published, sanitized export** in this repository,
not the private instance the workflow was developed on.

## [1.0.0] — 2026-08-03

First published release. Sanitized from a working n8n export; workflow logic
preserved exactly.

### Added
- Webhook trigger accepting Slack Events API payloads (`POST`).
- Slack event normalization into `message`, `channel`, `user`, `thread_ts`.
- Loop guard rejecting bot messages via `bot_id`, `subtype === "bot_message"`,
  and a configurable bot user ID.
- Input classifier producing ten `input_type` values: `windows`, `fortigate`,
  `paloalto`, `f5`, `cef`, `linux`, `wazuh_json`, `hash`, `ip`, `general`.
  Specific embedded log sources are tested before the generic Wazuh fallback.
- Switch routing on `input_type` with ten outputs.
- Seven source-specific SOC analyst system prompts: Wazuh, Windows, FortiGate,
  Palo Alto, F5 BIG-IP ASM, Trend Micro CEF, and general Q&A.
- Ollama inference via `POST /api/chat`, non-streaming, system + user messages.
- Response extraction and threaded Slack reply.

### Security
- All credential IDs and names replaced with placeholders.
- Instance ID, workflow ID, version ID and pinned execution data removed.
- Internal RFC 1918 addresses in the Ollama URL and in prompt examples replaced
  with RFC 5737 documentation addresses.
- A real public IPv4 address in a prompt NAT example replaced with `198.51.100.20`.
- Slack bot user ID replaced with the `SLACK_BOT_USER_ID` placeholder.
- Webhook path genericized to `ai-soc-assistant`, removing an organisation
  abbreviation.
- `active` forced to `false` so an import cannot start listening before review.

### Known issues
- Switch outputs for `ip`, `hash` and `linux` are not connected. Items routed
  there produce no reply and no error.
- No timeout, retry or error branch on the inference call.
- The model's reply is not parsed or validated before delivery.
- No Slack request signature verification.
- The `Detect Input Type` node contains a field literally named `=event_type`
  (stray `=` prefix). Preserved as-is; unread by the workflow.
- No threat-intelligence enrichment and no deterministic risk score.

[1.0.0]: https://github.com/maryamoah/soc-automation-playbooks/releases/tag/v1.0.0
