# Getting started

From clone to a working assistant. Budget 30–45 minutes, most of it Slack app
configuration and the first model pull.

## Prerequisites

| Requirement | Notes |
|---|---|
| n8n 1.40+ | Self-hosted. Must be reachable from Slack over HTTPS. |
| Ollama | Reachable **from n8n**, with a chat model pulled. |
| Slack workspace | You need permission to create and install an app. |
| Hardware | The largest prompt is ~31 KB. A 14B model on CPU works but is slow; a GPU with 12 GB+ is comfortable. |
| Python 3.9+ | Only for the validation scripts. |

## 1. Clone and inspect

```bash
git clone https://github.com/your-org/soc-automation-playbooks.git
cd soc-automation-playbooks
cp .env.example .env
```

`.env` is a worksheet. Nothing reads it automatically — the values get pasted
into the n8n UI. It exists so you have one place recording what you configured.

Confirm the repository is intact before trusting it:

```bash
python3 scripts/validate_json.py
python3 scripts/validate_examples.py
python3 scripts/scan_sensitive_values.py
```

## 2. Prepare Ollama

```bash
ollama pull qwen3:14b
ollama list
```

Then confirm n8n can reach it. This is the step people skip and then spend an
hour debugging:

```bash
# from the n8n host, or inside the n8n container
curl -s http://<ollama-host>:11434/api/tags
```

If n8n runs in Docker and Ollama on the host, `localhost` will not work — use
`host.docker.internal` (macOS/Windows) or the bridge gateway address (Linux).

## 3. Create the Slack app

Follow [`../workflows/n8n/ai-soc-assistant/credentials.md`](../workflows/n8n/ai-soc-assistant/credentials.md)
— scopes, event subscriptions, and the URL-verification handshake, which this
workflow does not answer on its own.

Summary: bot scopes `chat:write`, `channels:history` (and `groups:history` for
private channels); subscribe to `message.channels`; install to workspace; copy
the `xoxb-` token and the bot's member ID.

## 4. Import the workflow

n8n → *Workflows* → *Import from File* →
`workflows/n8n/ai-soc-assistant/ai-soc-assistant.sanitized.json`.

It imports **inactive**, with a placeholder credential that resolves to nothing.
That is deliberate: an export that activated itself on import would start
listening on a known path before you had reviewed it.

## 5. Replace the placeholders

Four values, detailed in
[`../workflows/n8n/ai-soc-assistant/configuration.md`](../workflows/n8n/ai-soc-assistant/configuration.md):

| Node | Field | Replace |
|---|---|---|
| `LLM (ollama)` | URL | `OLLAMA_BASE_URL` → real host |
| `LLM (ollama)` | body `model` | `qwen3:14b` → your model, if different |
| `Classifier` | loop guard | `SLACK_BOT_USER_ID` → your bot's `U…` id |
| `Send a message` | credential | select your real Slack credential |

Also change the webhook path from `ai-soc-assistant` to something unguessable.

## 6. Activate and register

Activate the workflow, copy the **production** webhook URL, and paste it into
the Slack app's *Event Subscriptions* request URL. Handle the challenge as
described in `credentials.md`.

Invite the bot: `/invite @your-bot-name`.

## 7. First test

Paste the `text` value from
[`../examples/inputs/wazuh-windows-alert.json`](../examples/inputs/wazuh-windows-alert.json)
into the channel. Within a minute you should get a threaded reply headed
`🪟 Windows Event Analysis`.

Then run the rest of the six-case set in
[`../workflows/n8n/ai-soc-assistant/testing.md`](../workflows/n8n/ai-soc-assistant/testing.md).
Cases 5 and 6 are supposed to produce *no reply* — that is the known dead-end
behaviour, not a broken install.

## If nothing happens

Work down this list before anything else:

1. Is the workflow **active**? The test URL only works with the editor open.
2. Did Slack **verify** the URL? Check *Event Subscriptions*.
3. Is the bot **in the channel**?
4. Does an execution appear in n8n at all? If not, the problem is Slack →
   webhook delivery, not the workflow.
5. If an execution exists but is green with no reply: check which Switch output
   the item took, and whether the loop guard fired.

Full symptom table:
[`../workflows/n8n/ai-soc-assistant/troubleshooting.md`](../workflows/n8n/ai-soc-assistant/troubleshooting.md).

## Before anyone relies on it

Read [`ai-safety-and-limitations.md`](ai-safety-and-limitations.md) and
[`human-in-the-loop.md`](human-in-the-loop.md) with whoever will be using the
output. The failure mode that matters is not the assistant breaking — it is the
assistant producing a fluent, confident, wrong assessment that an analyst
accepts because it reads like something a colleague wrote.
