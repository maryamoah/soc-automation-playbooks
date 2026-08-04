# Screenshots

Empty by design. No images are committed here yet.

## Read this before adding one

Screenshots are one of the most reliable ways to leak information from a
security project, because the leak is not in the file you were thinking about.
An n8n canvas screenshot and a Slack thread screenshot each routinely contain
several things that must not be published.

### What n8n canvas screenshots expose

- The subtitle under an HTTP Request node, which renders the **full URL** —
  including internal hostnames and private addresses
- The workflow name, if it encodes an organisation or project
- Credential names shown on a node
- The instance URL in the browser address bar
- Tab titles, bookmarks, other open tabs
- Execution history entries with real timestamps

### What Slack screenshots expose

- The **workspace name**, in the sidebar and window title
- **Channel names**, which frequently encode an organisation abbreviation
- Colleagues' names, avatars and presence
- Real alert content in the message being analysed — internal IPs, firewall
  hostnames, usernames, policy names
- Member counts, DM lists, unread badges
- The bot's own display name

That last group is the one that catches people: the *point* of the screenshot is
usually to show a real analysis, and a real analysis contains real telemetry.

## Redaction checklist

Before committing any image:

- [ ] Workspace, organisation, employer and university names removed
- [ ] Channel names replaced with generic ones
- [ ] Colleagues' names and avatars removed
- [ ] Internal hostnames replaced (e.g. `FW-EXAMPLE-01`)
- [ ] Private addressing replaced with RFC 5737 documentation addresses —
      `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`
- [ ] Any public IP that is real replaced
- [ ] Node URLs and subtitles redacted
- [ ] Credential names redacted
- [ ] Browser address bar, tabs and bookmarks cropped out
- [ ] Real alert content replaced with a synthetic example from
      [`../../examples/inputs/`](../../examples/inputs/)
- [ ] Timestamps that could correlate to a real incident altered or removed

## Redact by painting, not blurring

**Blur and pixelation are frequently reversible.** Both preserve the underlying
structure of the pixels, and text recovery from blurred or mosaiced regions is a
solved problem for anyone who cares to try.

Draw solid opaque rectangles at 100% opacity. Then flatten the image and
**re-export it** — do not just save the layered original, which may still carry
the unredacted layer.

Also strip metadata:

```bash
exiftool -all= screenshot.png
```

## Better than redacting

Take the screenshot in a scratch environment instead:

- an n8n instance with a generic workflow name and documentation-address nodes
- a fresh Slack workspace named something like `SOC Demo`, one channel, one
  member
- an event pasted from [`../../examples/inputs/`](../../examples/inputs/)

Nothing to redact, nothing to miss.

## Naming

```
ai-soc-assistant-canvas.png
ai-soc-assistant-slack-reply.png
```

Files matching `*-unredacted.*` and anything under `raw/` are git-ignored, so
you can keep an original locally without risking a commit.
