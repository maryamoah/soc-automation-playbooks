# Human-in-the-loop controls

The analyst is not a reviewer bolted onto an automated system. The analyst is
the decision-maker, and the system is a reading aid.

## Current controls

Four controls keep a human in the path. Three are structural — they hold because
of what the workflow **cannot do**, not because of a policy someone might
change.

### 1. No response actions exist

There is no node in this workflow capable of changing the state of any security
control. It cannot block an IP, isolate a host, disable an account, close an
alert or create a case. Its only outbound write is `chat.postMessage`.

This is the strongest control in the system precisely because it is not a
setting. There is nothing to misconfigure and no flag to flip.

### 2. Output is advisory text in a shared thread

The assessment lands in the thread the analyst started, in a channel, where
colleagues can see it and disagree with it. It is not injected into a ticket, a
case, or an alert queue where it would acquire the authority of a system record.

### 3. `Requires Investigation` is the mandated default

Every investigation prompt instructs the model to choose it whenever the
evidence cannot distinguish between benign and malicious explanations — rather
than guessing a verdict. This makes "I don't know" a first-class output.

### 4. A `Missing Information` section is required

Every report must state what would raise confidence. This turns the output from
a conclusion into a next-step list, and it makes a content-free verdict visibly
wrong: an assessment claiming certainty with an empty `Missing Information`
section on a thin event is self-evidently suspect.

## What the analyst is responsible for

The tool has produced a first pass. The analyst still:

- verifies the assessment against the source system;
- supplies the environmental context the model does not have — asset ownership,
  business purpose, change activity, what is normal here;
- decides the verdict;
- decides what action, if any, follows.

**Silence is not a result.** If no reply arrives, the assistant may have failed
or the input may have hit a dead-end route. Treating no-reply as "nothing
interesting" is a misreading the current implementation invites.

## Requirements for future response automation

None of this is implemented. It is written down now so that it is agreed before
anyone builds it, rather than negotiated afterwards under pressure.

| Requirement | Rationale |
|---|---|
| **No action on model verdict alone** | The verdict is generated text. Gate on deterministic signals. |
| **Explicit approval for consequential actions** | Blocking, isolation, disablement and case closure all require a named human to approve. |
| **Approval must present the evidence** | An approval prompt showing only "Block 203.0.113.30? [Yes]" trains people to click yes. Show the event, the reasoning and what will change. |
| **Reversibility documented first** | The rollback procedure ships before the action does. |
| **Full audit trail** | Event, model output, deterministic signals, approving human, timestamp, outcome. |
| **Fail closed** | If the approval step is unavailable, no action occurs. |
| **Rate limits on actions** | A bounded blast radius for a bug or an injection. |

### Why approval cannot be optional

Combine two threats from [`threat-model.md`](threat-model.md): an attacker can
influence log content (T4), and a model's verdict follows from what it reads.
Automate blocking on that verdict and you have built a mechanism where an
attacker chooses what your firewall blocks — including, potentially, your own
infrastructure.

Human approval is what breaks that chain. It is not procedural caution; it is
the control.

### Actions that may eventually be safe to automate

Reversible, low-impact, and useful even when wrong:

- adding an enrichment comment to an existing case
- tagging an alert for analyst attention
- gathering additional context from read-only sources
- opening a low-priority ticket for review

Anything that denies access, terminates a session, quarantines a file, or
closes an investigation stays behind approval.

## Approval-gate design notes

If and when a gate is built, three things determine whether it works:

**Approval fatigue is the failure mode.** A gate that fires constantly becomes a
reflex click. Gate rarely and meaningfully.

**Rejection must be as easy as approval, and its reason recorded.** Rejections
are the highest-value signal about where the model is wrong.

**Timeouts must expire to no-action.** An approval request that auto-approves
after an hour is not a control.
