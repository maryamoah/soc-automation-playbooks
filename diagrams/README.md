# Diagrams

Mermaid sources for the AI SOC Assistant. Every diagram is derived from
[`../workflows/n8n/ai-soc-assistant/ai-soc-assistant.sanitized.json`](../workflows/n8n/ai-soc-assistant/ai-soc-assistant.sanitized.json)
— nothing here is aspirational. Where a path is drawn as a dead end, it is a
dead end in the workflow.

GitHub does not render a bare `.mmd` file, so each source is embedded below as a
fenced `mermaid` block. Edit the `.mmd` file and paste the change here, or the
two drift apart.

| Source | Shows |
|---|---|
| [`architecture.mmd`](architecture.mmd) | End-to-end component flow |
| [`data-flow.mmd`](data-flow.mmd) | What data crosses which trust boundary — and what is never contacted |
| [`decision-flow.mmd`](decision-flow.mmd) | Classifier logic, in evaluation order |
| [`workflow-stages.mmd`](workflow-stages.mmd) | Stage sequence with the data contract between stages |

---

## Architecture

Solid paths exist in the export. The dashed path is real: `ip`, `hash` and
`linux` are classified, have Switch outputs, and connect to nothing.

```mermaid
flowchart TD
    A["Analyst pastes event in Slack"] --> B["Slack Events API"]
    B -->|"HTTP POST"| C["n8n Webhook<br/>POST /webhook/ai-soc-assistant"]

    C --> D["Normalize event<br/>(Set: message, channel, user, thread_ts)"]
    D --> E["Loop guard + classifier<br/>(Code node, JavaScript)"]

    E -->|"bot message<br/>or self-authored"| Z(["Drop — return []"])
    E --> F{"Switch on input_type"}

    F -->|wazuh_json| G1["Wazuh prompt"]
    F -->|windows| G2["Windows prompt"]
    F -->|fortigate| G3["FortiGate prompt"]
    F -->|paloalto| G4["Palo Alto prompt"]
    F -->|f5| G5["F5 BIG-IP ASM prompt"]
    F -->|cef| G6["Trend Micro CEF prompt"]
    F -->|general| G7["General SOC Q&A prompt"]
    F -.->|"ip / hash / linux<br/>classified but not wired"| X(["No output — see limitations"])

    G1 --> H
    G2 --> H
    G3 --> H
    G4 --> H
    G5 --> H
    G6 --> H
    G7 --> H

    H["LLM (ollama)<br/>POST OLLAMA_BASE_URL/api/chat<br/>model: OLLAMA_MODEL, stream: false"]
    H --> I["Extract response<br/>(Set: message.content)"]
    I --> J["Slack: reply in thread<br/>SLACK_CHANNEL_ID / thread_ts"]
    J --> K["Analyst reviews and decides"]

    style Z fill:#3a3a3a,color:#fff
    style X fill:#5a3a3a,color:#fff
    style K fill:#2d4a2d,color:#fff
```

---

## Data flow

Note the `Not contacted by this workflow` cluster. Threat-intelligence
enrichment, case management and every security control sit outside the system —
there is no write path to any of them.

```mermaid
flowchart LR
    subgraph SLACK["Slack workspace (SaaS — third party)"]
        S1["Analyst message<br/>raw log / alert JSON"]
        S2["Threaded reply<br/>plain-text assessment"]
    end

    subgraph EDGE["Network edge"]
        P["Reverse proxy<br/>(RECOMMENDED — not implemented)<br/>TLS + Slack signature verification"]
    end

    subgraph N8N["n8n instance (self-hosted)"]
        W["Webhook<br/>no auth configured"]
        N["Normalize"]
        CL["Classify + loop guard"]
        PR["Prompt selection"]
        EX["Extract response"]
        CRED[("Credential store<br/>Slack bot token<br/>encrypted at rest")]
    end

    subgraph LLM["Ollama host (self-hosted)"]
        O["POST /api/chat<br/>system prompt + event text"]
        M[("Model weights<br/>OLLAMA_MODEL")]
    end

    subgraph NOTUSED["Not contacted by this workflow"]
        TI["VirusTotal / AbuseIPDB<br/>PLANNED"]
        CM["TheHive / Cortex / OpenCTI<br/>PLANNED"]
        FW["Firewalls / EDR / IAM<br/>NO WRITE PATH EXISTS"]
    end

    S1 -->|"event text<br/>may contain hostnames,<br/>usernames, internal IPs"| P
    P --> W
    W --> N --> CL --> PR
    PR -->|"system_prompt + message"| O
    O --> M
    O -->|"message.content"| EX
    EX --> S2
    CRED -.->|"bot token"| S2

    PR -.->|"no call"| TI
    EX -.->|"no call"| CM
    EX -.->|"no call"| FW

    style NOTUSED fill:#3a2a2a,color:#fff
    style P stroke-dasharray: 5 5
```

---

## Decision flow

This mirrors the Code node exactly, including evaluation order. Order matters:
specific log sources are tested before the generic `wazuh_json` fallback, which
is why a Wazuh document wrapping a FortiGate log reaches the FortiGate analyst
prompt — and also why Wazuh alerts tagged `linux` reach a dead end.

```mermaid
flowchart TD
    START(["Item from Detect Input Type"]) --> LOOP{"bot_id set<br/>OR subtype = bot_message<br/>OR user = SLACK_BOT_USER_ID?"}
    LOOP -->|yes| DROP(["return [] — nothing runs"])
    LOOP -->|no| RAW["rawInput = message ?? text ?? body ?? input ?? ''"]

    RAW --> PARSE{"JSON.parse succeeds?"}

    PARSE -->|yes — structured path| S1{"data.win OR eventID OR providerName<br/>OR decoder = windows_eventchannel<br/>OR group windows / windows_security?"}
    S1 -->|yes| W["input_type = windows"]
    S1 -->|no| S2{"fortigate in decoder / groups / text?"}
    S2 -->|yes| FG["input_type = fortigate"]
    S2 -->|no| S3{"paloalto / palo alto / pan-os?"}
    S3 -->|yes| PA["input_type = paloalto"]
    S3 -->|no| S4{"f5 / f5-bigip / big-ip?"}
    S4 -->|yes| F5["input_type = f5"]
    S4 -->|no| S5{"CEF marker AND<br/>Trend Micro product marker?"}
    S5 -->|yes| CEF["input_type = cef"]
    S5 -->|no| S6{"linux / auth.log / sshd[ ?"}
    S6 -->|yes| LX["input_type = linux"]
    S6 -->|no| S7{"rule OR agent OR manager OR cluster<br/>OR _index starts with wazuh-?"}
    S7 -->|yes| WZ["input_type = wazuh_json"]
    S7 -->|no| GEN["input_type = general"]

    PARSE -->|no — text path| T1{"windows keywords?"}
    T1 -->|yes| W
    T1 -->|no| T2{"fortigate / fortios?"}
    T2 -->|yes| FG
    T2 -->|no| T3{"palo alto / pan-os?"}
    T3 -->|yes| PA
    T3 -->|no| T4{"f5-bigip / big-ip / asm:?"}
    T4 -->|yes| F5
    T4 -->|no| T5{"Trend Micro CEF header?"}
    T5 -->|yes| CEF
    T5 -->|no| T6{"32 / 40 / 64 hex chars?"}
    T6 -->|yes| HS["input_type = hash"]
    T6 -->|no| T7{"IPv4 present AND<br/>at most 3 tokens?"}
    T7 -->|yes| IP["input_type = ip"]
    T7 -->|no| GEN

    W --> OUT
    FG --> OUT
    PA --> OUT
    F5 --> OUT
    CEF --> OUT
    WZ --> OUT
    GEN --> OUT

    LX --> DEAD
    HS --> DEAD
    IP --> DEAD

    OUT(["Switch → prompt node → Ollama → Slack"])
    DEAD(["Switch output not connected<br/>NO REPLY, NO ERROR"])

    style DROP fill:#3a3a3a,color:#fff
    style DEAD fill:#5a3a3a,color:#fff
```

---

## Workflow stages

```mermaid
sequenceDiagram
    autonumber
    actor Analyst
    participant Slack
    participant WH as Webhook
    participant NM as Detect Input Type<br/>(normalize)
    participant CD as Classifier<br/>(guard + classify)
    participant SW as Route Investigation
    participant PR as prompt node<br/>(1 of 7 selectors)
    participant OL as Ollama
    participant EX as Compiler<br/>(extract)

    Analyst->>Slack: paste alert / question
    Slack->>WH: POST event_callback
    WH-->>Slack: 200 immediately (onReceived)
    Note over WH,Slack: Response says nothing about<br/>whether analysis succeeded

    WH->>NM: { body: { event } }
    NM->>CD: { message, channel, user, thread_ts, "=event_type" }

    alt bot or self-authored message
        CD-->>CD: return [] — execution ends silently
    else human message
        CD->>SW: + { input_type }
        alt input_type is ip / hash / linux
            SW-->>SW: unconnected output — no reply, no error
        else routed type
            SW->>PR: item
            PR->>OL: + { system_prompt }
            Note over PR,OL: POST /api/chat<br/>system = system_prompt<br/>user = message (raw, unfiltered)
            OL->>EX: { message: { content } }
            EX->>Slack: { response, channel, thread_ts }
            Slack->>Analyst: threaded plain-text assessment
            Note over Analyst: Advisory only.<br/>Analyst decides what happens next.
        end
    end
```
