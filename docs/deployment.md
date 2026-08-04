# Deployment

Production considerations. The workflow runs happily on a laptop; running it
where analysts depend on it needs more.

## Topology

```
Slack (SaaS)
   │  HTTPS
   ▼
Reverse proxy  ← TLS termination, Slack signature verification, rate limiting
   │
   ▼
n8n  ← workflow, credential store, execution history
   │  HTTP (private network)
   ▼
Ollama  ← model weights, GPU
```

The reverse proxy layer is **not implemented by this repository** and is the
most important thing you add. See [`security-model.md`](security-model.md).

## Placement

| Component | Where | Why |
|---|---|---|
| n8n | Private network, published through a proxy | Only the webhook path needs to be reachable from Slack |
| Ollama | Private network, bound to a private interface | Ollama has no authentication of its own |
| Proxy | DMZ | Terminates TLS, verifies Slack signatures, applies rate limits |

Do not put Ollama on the internet. `OLLAMA_HOST=127.0.0.1:11434` plus a firewall
rule permitting only the n8n host is the baseline.

## n8n configuration

```bash
N8N_ENCRYPTION_KEY=<generated once, backed up>
N8N_HOST=n8n.example.com
N8N_PROTOCOL=https
WEBHOOK_URL=https://n8n.example.com/
N8N_BLOCK_ENV_ACCESS_IN_NODE=true
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_MAX_AGE=168
N8N_CONCURRENCY_PRODUCTION_LIMIT=4
```

`N8N_ENCRYPTION_KEY` deserves emphasis: it encrypts stored credentials. Lose it
and every credential in the instance must be recreated manually. Back it up
somewhere that is not the same host.

`EXECUTIONS_DATA_MAX_AGE` matters more here than in a typical n8n deployment,
because execution history contains the **full text of every security event
analysts pasted**. That is a data-retention decision, not a housekeeping one —
see [`observability.md`](observability.md#execution-history-is-sensitive).

Use PostgreSQL rather than the default SQLite for anything shared.

## Ollama sizing

The prompts are large: ~7 KB (Wazuh) to ~31 KB (Palo Alto), roughly 2k–9k tokens
before the event is appended.

- **Context window** must comfortably exceed prompt + event + response.
  A model that silently truncates will drop the output-format instructions,
  which live at the *end* of most prompts.
- **VRAM**: a 14B model at 4-bit quantisation needs roughly 10–12 GB. CPU-only
  works and is slow enough that analysts will stop waiting.
- **Keep-alive**: set `OLLAMA_KEEP_ALIVE` generously so the model is not
  reloaded between alerts.

Measure before rollout:

```bash
time curl -s http://<ollama-host>:11434/api/chat -d @large-prompt-test.json
```

## Concurrency and cost

There is no rate limiting in this workflow. Every message in a channel the bot
is in becomes an inference request. Bound it:

- `N8N_CONCURRENCY_PRODUCTION_LIMIT` at the orchestrator
- rate limiting at the proxy, per source
- restrict the bot to specific channels

A busy `#security-alerts` channel with the bot present will generate continuous
load. Start with a dedicated low-traffic channel.

## Hardening checklist

- [ ] Webhook path is unguessable
- [ ] Proxy verifies `X-Slack-Signature` and rejects stale timestamps
- [ ] Ollama not reachable from outside the private network
- [ ] `N8N_ENCRYPTION_KEY` set explicitly and backed up
- [ ] `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`
- [ ] Execution data pruning configured to your retention policy
- [ ] n8n behind authentication for editor access
- [ ] TLS everywhere Slack can see
- [ ] Timeout and retry configured on `LLM (ollama)`
- [ ] Error branch notifying the analyst on failure
- [ ] Bot invited only to intended channels

## Upgrades

**n8n**: the export declares node typeVersions (`webhook` 2.1, `set` 3.4,
`switch` 3.4, `httpRequest` 4.3, `code` 2, `slack` 2.4). Major n8n upgrades
occasionally change node behaviour; re-run the six-case test set afterwards.

**Model**: changing `OLLAMA_MODEL` is a behavioural change, not a config tweak.
Re-run the full test set and specifically re-check format adherence and
over-claiming. Record the model version alongside the results.

**Prompts**: the highest-risk edit in the system. These prompts are mostly
negative constraints — "never conclude", "do not treat as proof" — and tidying
the wording is an easy way to delete a guard rail. Diff before and after.

## Backup

- Workflow JSON (sanitized, in version control)
- `N8N_ENCRYPTION_KEY`
- n8n database
- Slack app manifest

Credentials are not in version control by design. Recreating them is a
documented, deliberate step.
