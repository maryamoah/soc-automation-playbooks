# Credentials

The workflow needs exactly one credential: a Slack API credential on the
`Send a message` node. Ollama is called without authentication.

**Nothing in this repository contains a credential value, credential ID,
credential name, token, signing secret, channel ID or workspace identifier.**
The export ships with `SLACK_CREDENTIAL_ID` / `SLACK_API_CREDENTIAL`, which
resolve to nothing in your instance — you must create and select a real one.

---

## Slack

### Required scopes

Create a Slack app (*from scratch*) at <https://api.slack.com/apps> and add these
**Bot Token Scopes** under *OAuth & Permissions*:

| Scope | Why |
|---|---|
| `chat:write` | Post the analysis reply |
| `channels:history` | Receive `message.channels` events from public channels |
| `groups:history` | Same, for private channels — omit if you only use public |

`chat:write.public` is optional and lets the bot post to public channels it has
not joined. Leave it off unless you need it: requiring an explicit invite is a
useful boundary on where security event data gets discussed.

Do **not** add `users:read`, `files:read`, `channels:read` or admin scopes. The
workflow uses none of them, and every extra scope widens what a leaked token
gives away.

### Event subscriptions

Under *Event Subscriptions*, enable events and subscribe to these **bot events**:

- `message.channels` — public channels
- `message.groups` — private channels (only if you added `groups:history`)

Set the **Request URL** to your n8n production webhook:

```
https://<your-n8n-host>/webhook/<your-webhook-path>
```

### URL verification

Slack verifies the URL by POSTing

```json
{ "type": "url_verification", "challenge": "3eZbrw1a...", "token": "..." }
```

and requires the `challenge` value echoed back within three seconds.

**This workflow does not implement that handshake.** The Webhook node uses the
default immediate response, which returns `{"message": "Workflow was started"}`,
and Slack rejects it. Three ways forward:

1. **Temporary responder (simplest).** In n8n, build a throwaway workflow: a
   Webhook node on the same path with *Respond* set to *Using Respond to
   Webhook*, wired to a Respond to Webhook node returning
   `={{ $json.body.challenge }}`. Activate it, let Slack verify, deactivate it,
   then activate the real workflow. Slack only re-verifies when the URL changes.
2. **Handle it in this workflow.** Set the Webhook node's *Respond* to *Using
   Respond to Webhook*, add an IF node on
   `{{ $json.body.type === "url_verification" }}` before `Detect Input Type`, and send
   the true branch to a Respond to Webhook node echoing the challenge. This is
   the durable fix and is on the roadmap.
3. **Handle it at the proxy.** If you front n8n with a reverse proxy that
   verifies Slack signatures (recommended anyway — see below), answer
   `url_verification` there and never pass it through.

### Creating the n8n credential

In n8n: *Credentials* → *New* → **Slack API** → paste the **Bot User OAuth
Token** (`xoxb-…`, from *OAuth & Permissions* after installing the app to your
workspace) → *Save*. Then open the workflow, select `Send a message`, and pick
the credential from the dropdown.

Use the **Slack API** credential type (token-based), not **Slack OAuth2**. The
node in the export declares `slackApi`; selecting OAuth2 requires changing the
node's authentication method.

Finally, invite the bot to the channel: `/invite @your-bot-name`. Without this,
`chat:write` returns `not_in_channel` and no reply appears.

### The signing secret

Slack also issues a **Signing Secret** (*Basic Information* → *App
Credentials*). Every request Slack sends carries `X-Slack-Signature` and
`X-Slack-Request-Timestamp`, which the secret lets you verify.

**This workflow does not verify signatures.** The signing secret is therefore
unused by the export — it is listed in `.env.example` for the verifying proxy
you should put in front of n8n, not for n8n itself. Without verification, the
webhook accepts a forged POST from anyone who knows the URL. See
[`../../../docs/security-model.md`](../../../docs/security-model.md#unauthenticated-webhook)
for proxy configuration.

---

## Ollama

**No credential.** The `LLM (ollama)` node performs an unauthenticated `POST` to
`OLLAMA_BASE_URL/api/chat`. Ollama has no built-in authentication.

This is acceptable only when the Ollama host is not reachable from anywhere you
do not control. Bind it to localhost or a private interface
(`OLLAMA_HOST=127.0.0.1:11434`), keep it off the internet, and restrict inbound
`11434` to the n8n host.

If you must expose it, put it behind a reverse proxy that requires a header
token, then in n8n:

1. *Credentials* → *New* → **Header Auth** → name `Authorization`, value
   `Bearer <token>`.
2. On `LLM (ollama)`: *Authentication* → *Generic Credential Type* → *Header
   Auth* → select it.

Same applies if you point the URL at a hosted inference API — but note that
doing so sends log content, including whatever internal hostnames, usernames and
IP addresses appear in it, to a third party. That is a materially different data
protection posture from the local-model design this workflow assumes. Get it
approved before you make the change.

---

## Credential hygiene

- **Never commit a token.** [`.gitignore`](../../../.gitignore) excludes `.env`
  and `*.local.json`; [`secret-scan.yml`](../../../.github/workflows/secret-scan.yml)
  fails the build if one appears anyway.
- **Re-sanitize before publishing any export.** n8n embeds credential IDs and
  names in exported JSON. Run
  `python3 scripts/sanitize_n8n_export.py raw.json clean.json --report` — it
  strips them, drops the instance ID and pinned data, forces `active: false`,
  and refuses to exit cleanly if a known-bad pattern survives.
- **Rotate on exposure.** If a `xoxb-` token reaches a repository, a log, a
  screenshot or a chat message, revoke it in the Slack app configuration and
  issue a new one. Reinstalling the app rotates the bot token.
- **One credential per workflow per environment.** Shared credentials make
  rotation an outage.
- **Set `N8N_ENCRYPTION_KEY` explicitly** and back it up. n8n encrypts stored
  credentials with it; lose it and every credential in the instance must be
  recreated by hand.
