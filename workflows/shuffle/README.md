# Shuffle workflows

> **Shuffle is not used in this project.**
>
> No Shuffle instance has been deployed. No Shuffle workflow has been built. No
> Shuffle export exists here, and none is planned in the near term.
>
> Everything implemented in this repository runs on **n8n + Ollama + Slack**.

## Why this directory exists at all

These are design notes, not deliverables. They exist because the problems they
describe are real and distinct from what the implemented workflow solves — and
writing the design down is how you find out that a playbook needs an approval
gate *before* you build it.

Read them as "what a SOAR layer would need to look like if this project ever
adopted one", not as work in progress. Shuffle is named because it is the
obvious open-source candidate, not because it is installed.

Publishing a fabricated `.json` export to make the directory look complete would
misrepresent the project — and a plausible-looking SOAR playbook that has never
run is worse than an empty directory, because someone might deploy it.

## Design notes

| Design note | Purpose | Status |
|---|---|---|
| [wazuh-thehive-cortex.md](planned/wazuh-thehive-cortex.md) | Wazuh alert → TheHive case → Cortex analyzers → analyst notification | Not built |
| [threat-intelligence-enrichment.md](planned/threat-intelligence-enrichment.md) | Indicator extraction and multi-source reputation lookup | Not built |
| [automated-response.md](planned/automated-response.md) | Approval-gated containment actions | Not built |

## Relationship to the n8n workflow

They solve different problems and are not competing implementations.

The **AI SOC Assistant** (n8n, implemented) is analyst-initiated: a human pastes
an event and gets a reading aid back. It has no state and no write path into
security infrastructure.

The **Shuffle designs** are alert-initiated: an alert fires and a playbook runs
without a human starting it. That is a materially different risk profile — an
automated playbook acts on events nobody has looked at yet, which is exactly why
[`automated-response.md`](planned/automated-response.md) is gated on approval
rather than on a verdict.

## If this project ever adopts Shuffle

Adopting a second automation platform is a real decision with real cost — a
second instance to run, patch and secure, a second credential store, and a
second place where a workflow can break. None of that is justified by the
current scope. These notes exist so the decision can be made deliberately later,
with the designs already thought through.

## What implementing one would require

Per [`../../docs/workflow-lifecycle.md`](../../docs/workflow-lifecycle.md), a
design becomes `Implemented` only when all of the following exist:

1. A working Shuffle workflow, actually run against real alerts.
2. A sanitized export committed here.
3. The full documentation set: README, configuration, credentials, node
   reference, testing, troubleshooting, changelog.
4. Synthetic examples.
5. Status updated in **both** the root README and this file.

Until every one of those exists, the item stays `Not built`, in every table
where it appears.
