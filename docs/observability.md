# Observability

What you can see, what you cannot, and what to add.

## What exists today

**n8n execution history** is the only observability in the system. Per
execution: status, duration, and the full input and output of every node.

That is enough to answer "what happened to this specific message" and almost
nothing else. There is no metric, no dashboard, no alert, and no aggregate view.

## Execution history is sensitive

Execution history stores the **full text of every security event anyone has
pasted** — hostnames, usernames, private addressing, command lines, incident
detail — alongside the full system prompts and the model's output.

Treat it as a security telemetry archive, because that is what it is:

```bash
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_MAX_AGE=168        # hours; match your retention policy
EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
EXECUTIONS_DATA_SAVE_ON_ERROR=all
```

Retention here is a policy decision, not a disk-space decision. Restrict n8n
editor access accordingly.

## The observability gap that matters

**Silent failures are invisible.**

Two failure modes complete as *successful* executions with no output:

1. The loop guard fires — correct behaviour, indistinguishable in the execution
   list from case 2.
2. An item routes to Switch output 0 (`ip`), 1 (`hash`) or 4 (`linux`), all
   unconnected.

Neither produces an error, so no error alerting will ever fire. An analyst who
gets no reply cannot tell whether the assistant declined, dropped the input, or
crashed — and the execution list will not tell you either without opening the
execution and inspecting which output the item took.

Interim detection, until the routes are wired:

- Filter executions where the `Send a message` node did not run.
- Add a NoOp node on each unused Switch output purely so the execution shows
  where the item went.

## What to add

In rough order of value.

### 1. Error notification

There is no error branch. An Ollama timeout produces a failed execution and
silence in the channel. Configure an n8n **error workflow** that posts to a
maintenance channel with the workflow name, execution ID and error.

Better still, set *On Error → Continue (using error output)* on `LLM (ollama)`
and reply in the analyst's own thread: "analysis failed, please retry". Silence
is the worst response to someone who is waiting.

### 2. Latency tracking

Inference dominates. Record duration per `input_type` — the ~31 KB Palo Alto
prompt behaves very differently from the ~1.6 KB general prompt. You need this
before you can size hardware or set a sensible timeout.

### 3. Classification distribution

Count executions by `input_type`. This tells you which prompts are earning their
maintenance, and it is how you will discover that a meaningful share of traffic
is landing on the dead-end routes.

### 4. Delivery rate

Executions where `Send a message` ran, over total executions. A drop is the
earliest signal that something is broken.

### 5. Output quality sampling

The metric that actually matters, and the only one requiring humans. Sample
outputs against analyst ground truth and track: verdict agreement, over-claiming
(blocked traffic described as compromise), unsupported MITRE mappings, and
format compliance.

Without this, a model upgrade that quietly degrades analysis looks identical to
one that improves it. See
[`ai-safety-and-limitations.md`](ai-safety-and-limitations.md#measuring-whether-it-helps).

## Health checks

```bash
# Ollama up, model loaded
curl -sf http://<ollama-host>:11434/api/tags || echo "OLLAMA DOWN"
ollama ps

# n8n reachable
curl -sf https://<n8n-host>/healthz || echo "N8N DOWN"

# Slack token valid
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
     https://slack.com/api/auth.test
```

`ollama ps` is worth watching: if the model has been evicted, the next request
pays the full load time and will probably time out.

## What not to log

- Full event text into any system with weaker access control than n8n
- Slack tokens, in any form, at any log level
- The webhook URL — it is the access control
- Model output verbatim into a shared log, unless retention is understood
