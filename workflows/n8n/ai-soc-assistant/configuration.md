# Configuration

Every value that must change before the workflow will run, and where it lives.

The shipped export contains **literal placeholder strings**, not environment
variable references. n8n blocks `$env` access inside nodes by default
(`N8N_BLOCK_ENV_ACCESS_IN_NODE=true`), so a `{{ $env.OLLAMA_BASE_URL }}`
expression would fail silently on most installs. Obvious broken placeholders
fail loudly instead, which is the safer default for a published workflow. If you
have deliberately enabled env access, see
[Using environment variables](#using-environment-variables) at the end.

---

## Required — the workflow will not work without these

### 1. `OLLAMA_BASE_URL`

**Node:** `LLM (ollama)` → **URL**

| Shipped | Replace with |
|---|---|
| `OLLAMA_BASE_URL/api/chat` | `http://<your-ollama-host>:11434/api/chat` |

The host must be reachable **from the n8n container**, not from your laptop. In
Docker Compose with both services on one network this is the service name
(`http://ollama:11434/api/chat`); with n8n in Docker and Ollama on the host it
is `http://host.docker.internal:11434/api/chat` on macOS/Windows, or the bridge
gateway address on Linux. `localhost` inside a container means the container.

Verify from inside the n8n container before blaming the workflow:

```bash
docker exec -it <n8n-container> \
  wget -qO- http://<your-ollama-host>:11434/api/tags
```

### 2. `OLLAMA_MODEL`

**Node:** `LLM (ollama)` → **JSON body** → `model`

The export ships with `qwen3:14b`, which is what this workflow was built and
tested against. That is not a placeholder — it is a real, working default —
but the model must be pulled on your Ollama host or the request returns a 404:

```bash
ollama pull qwen3:14b
```

Substituting a model is fine, with two caveats. **Context window:** the
FortiGate and Palo Alto system prompts are ~22 KB and ~31 KB, roughly 6–9k
tokens before the event is appended. A model with a small context window will
silently truncate the prompt and drop the output-format instructions. **Format
adherence:** the prompts demand strict plain-text sections; smaller models drift
back into Markdown. Test with
[`testing.md`](testing.md) before switching.

If your model emits reasoning blocks (`<think>…</think>`), that text will appear
in Slack — nothing strips it. Either pick a model that suppresses reasoning in
its response field, or add a cleanup step in `Compiler`.

### 3. `SLACK_BOT_USER_ID`

**Node:** `Classifier` → line 9 of the loop guard

```js
eventUser === 'SLACK_BOT_USER_ID'
```

Replace with your bot's member ID — starts with `U`, eleven characters, e.g.
`U0XXXXXXXXX`. Find it in Slack: *Apps* → your app → *Bot User* → *Member ID*,
or via `auth.test`:

```bash
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  https://slack.com/api/auth.test | grep user_id
```

This is a **loop-prevention control**. The other two guard conditions (`bot_id`
and `subtype === 'bot_message'`) catch most cases, so an unreplaced placeholder
will not obviously break anything — until a configuration in which Slack sends
neither, and the assistant starts answering its own replies in a loop that
consumes GPU until someone notices. Replace it.

### 4. Slack credential

**Node:** `Send a message` → **Credential to connect with**

Ships as a placeholder reference (`SLACK_CREDENTIAL_ID` /
`SLACK_API_CREDENTIAL`) that does not resolve to anything in your instance.
Create a real credential and select it. Full setup:
[`credentials.md`](credentials.md).

---

## Strongly recommended

### 5. Webhook path

**Node:** `Webhook` → **Path**

Ships as `ai-soc-assistant`, giving
`https://<n8n-host>/webhook/ai-soc-assistant`. Change it. A guessable path on an
unauthenticated webhook that fronts a GPU is a resource-exhaustion invitation
and, worse, a free channel into your LLM. Use a random component:

```bash
python3 -c "import secrets; print('soc-' + secrets.token_hex(16))"
```

Then update the Slack app's Event Subscriptions request URL to match. Treat the
resulting URL as a secret — it is the only thing standing between the internet
and your inference host. This is a weak control on its own; combine it with
network restrictions or a verifying proxy per
[`../../../docs/security-model.md`](../../../docs/security-model.md).

### 6. Timeout and retry on the inference call

**Node:** `LLM (ollama)` → **Options** → *Timeout*, and node settings → *Retry
on Fail*

Not configured in the export. A 14B model answering a 31 KB prompt can take 30–90
seconds on modest hardware, and n8n's default HTTP timeout will cut it off.
Suggested: timeout 120000 ms, retry twice with 5000 ms between tries. Also set
*On Error* → *Continue (using error output)* and wire a Slack node that tells
the analyst the assistant failed — silence is the worst failure mode for a tool
someone is waiting on.

---

## Configuration reference

Mirrors [`.env.example`](../../../.env.example). These names are documentation
labels for values you paste into the n8n UI; the workflow does not read a `.env`
file.

| Name | Where it lands | Required | Ships as |
|---|---|---|---|
| `N8N_BASE_URL` | Your n8n instance URL — used to build the webhook URL | Yes | — |
| `WAZUH_WEBHOOK_PATH` | `Webhook` → Path | Yes | `ai-soc-assistant` |
| `OLLAMA_BASE_URL` | `LLM (ollama)` → URL | Yes | placeholder |
| `OLLAMA_MODEL` | `LLM (ollama)` → body `model` | Yes | `qwen3:14b` |
| `SLACK_BOT_TOKEN` | Inside the n8n Slack credential | Yes | not in repo |
| `SLACK_SIGNING_SECRET` | Your verifying proxy — **not used by the workflow** | No | not in repo |
| `SLACK_BOT_USER_ID` | `Classifier` loop guard | Yes | placeholder |
| `SLACK_CHANNEL_ID` | Resolved at runtime from the event; not configured | No | — |
| `VIRUSTOTAL_API_KEY` | Planned enrichment | No | unused |
| `ABUSEIPDB_API_KEY` | Planned enrichment | No | unused |
| `THEHIVE_URL` | Planned case management | No | unused |
| `CORTEX_URL` | Planned analyzers | No | unused |
| `OPENCTI_URL` | Planned correlation | No | unused |

The last five have no node in this workflow. They are listed so the intended
end-state configuration is visible in one place, and they are marked unused
everywhere they appear.

`SLACK_CHANNEL_ID` deserves a note: there is no channel configuration in this
workflow. `Send a message` uses `{{ $json.channel }}` from the inbound event, so
the assistant replies wherever it was addressed. To pin it to one channel,
replace that expression with a literal ID — and expect replies to leave the
thread they came from unless you also pin `thread_ts`.

---

## Post-configuration checklist

- [ ] `LLM (ollama)` URL contains a real scheme and host, no `OLLAMA_BASE_URL`
- [ ] Model in the body expression is pulled on the Ollama host
- [ ] `Classifier` contains a real `U…` bot ID, no `SLACK_BOT_USER_ID`
- [ ] `Send a message` shows a green, saved credential
- [ ] Webhook path changed from the shipped default
- [ ] Slack app Event Subscriptions URL matches the production webhook URL
- [ ] Bot invited to the target channel
- [ ] Workflow activated (the test URL only works with the editor open)
- [ ] A test event from [`testing.md`](testing.md) returns a threaded reply

Verify no placeholders survive:

```bash
grep -o 'OLLAMA_BASE_URL\|SLACK_BOT_USER_ID\|SLACK_CREDENTIAL_ID' your-configured-export.json
```

Silence means clean.

---

## Using environment variables

If you run n8n with `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, you can replace the
literals with expressions:

| Node | Field | Expression |
|---|---|---|
| `LLM (ollama)` | URL | `={{ $env.OLLAMA_BASE_URL }}/api/chat` |
| `LLM (ollama)` | body `model` | `model: $env.OLLAMA_MODEL` |
| `Classifier` | loop guard | `eventUser === $env.SLACK_BOT_USER_ID` |

Understand the trade-off before doing this. Disabling env blocking makes *every*
environment variable — including `N8N_ENCRYPTION_KEY` and database credentials —
readable from any Code node in the instance. On a multi-user n8n, that is a
privilege escalation path. On a single-operator instance it is a reasonable
convenience. See
[`../../../docs/secrets-management.md`](../../../docs/secrets-management.md).
