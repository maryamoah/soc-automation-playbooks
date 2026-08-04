# Setup and publishing

Two audiences: people **uploading this repository to GitHub**, and people
**forking it** to publish their own copy.

---

## Uploading to GitHub — read this first

**GitHub's web drag-and-drop uploader silently skips files and folders whose
name begins with a dot.** It reports success, because as far as it is concerned
nothing went wrong. These are the files it will drop:

```
.github/                 all CI workflows, issue templates, CODEOWNERS, dependabot
.gitignore
.env.example
```

Losing them is not cosmetic:

| Missing | Consequence |
|---|---|
| `.github/workflows/` | No CI. The README status badges point at workflows that do not exist, so they render as broken or empty — which looks worse than having no badges. |
| `.gitignore` | **`scripts/sanitize-map.json` is no longer ignored.** That file's keys are your real internal addresses, hostnames and Slack bot ID. One `git add .` publishes them. |
| `.env.example` | The configuration reference the README links to returns 404. |

### Use one of these instead

**Option A — github.dev (browser only, no install).**

1. Open the repository on GitHub and press the **`.`** key. This opens
   github.dev, a full VS Code editor in the browser.
2. Drag the entire unzipped folder — or just `.github/`, `.gitignore` and
   `.env.example` — into the file explorer pane on the left. It handles
   dotfiles correctly.
3. Click the **Source Control** icon, enter a commit message, and press
   **Commit & Push**.

**Option C — GitHub's "Create new file" (pure web, no editor).**

The drag-and-drop uploader skips dotfiles, but the *file creator* does not. On
the repository page choose **Add file → Create new file**, then type the full
path into the filename box, including the directories:

```
.github/workflows/secret-scan.yml
```

GitHub creates the folders as you type each `/`. Paste the file contents, commit,
repeat. Slow — there are ten files under `.github/` — but it works with nothing
but a browser, and it is the reliable fallback if github.dev misbehaves.

Files to create this way:

```
.github/workflows/json-validation.yml
.github/workflows/markdown-lint.yml
.github/workflows/secret-scan.yml
.github/workflows/python-validation.yml
.github/ISSUE_TEMPLATE/bug_report.yml
.github/ISSUE_TEMPLATE/feature_request.yml
.github/ISSUE_TEMPLATE/workflow_request.yml
.github/pull_request_template.md
.github/CODEOWNERS
.github/dependabot.yml
.gitignore
.env.example
```

**Option B — git on the command line.**

```bash
cd soc-automation-playbooks
git init -b main
git add .
git status          # confirm .github/, .gitignore and .env.example are listed
git commit -m "feat: initial release — AI SOC Assistant n8n workflow"
git remote add origin git@github.com:maryamoah/soc-automation-playbooks.git
git push -u origin main
```

The `git status` line matters. It is the last cheap moment to notice a missing
dotfile, a stray `.env`, or a screenshot you meant to redact.

### Verify the upload worked

Visit these three URLs. All must return a page, not a 404:

```
https://github.com/maryamoah/soc-automation-playbooks/tree/main/.github/workflows
https://github.com/maryamoah/soc-automation-playbooks/blob/main/.gitignore
https://github.com/maryamoah/soc-automation-playbooks/blob/main/.env.example
```

Then open the **Actions** tab. Within a minute or two you should see runs for
JSON validation, Secret scan, Python validation and Markdown lint. Once they
pass, the README badges turn green.

---

## Repository settings

Worth five minutes; the About panel is what shows in search results and on your
pinned-repository grid.

**About** (gear icon, top right of the repository page):

> Description
> `AI-assisted SOC triage with n8n and a locally hosted LLM. Sanitized, importable workflow exports with full documentation.`

> Topics
> `soc` `security-automation` `soar` `n8n` `ollama` `wazuh` `slack` `llm` `blue-team` `incident-response` `threat-detection` `siem`

**Settings → Code security:** enable **secret scanning** and **push
protection**. Push protection blocks a commit containing a recognised token
*before* it reaches GitHub — the only control here that acts before exposure
rather than after it. This repository's own scanner runs after the push; treat
them as complementary.

**Settings → Actions → General:** set workflow permissions to **read-only**.
Nothing here needs write access to itself.

**Optional — branch protection.** Useful once others contribute, unnecessary
friction while it is only you. If you enable it, require JSON validation, Secret
scan and Python validation. Leave Markdown lint out; it is advisory by design.

---

## What CI will report

| Workflow | Expected |
|---|---|
| JSON validation | Pass |
| Secret scan | Pass |
| Python validation | Pass |
| Markdown lint | Link check passes; markdownlint is advisory (`continue-on-error: true`) and will likely flag cosmetic line-length findings |

Markdown lint is deliberately non-blocking. A style nit should not turn a
contributor's documentation fix into a red build.

---

## Before re-exporting the workflow from your own n8n

Only needed if you modify the workflow and want to republish it.

```bash
cp scripts/sanitize-map.example.json scripts/sanitize-map.json
$EDITOR scripts/sanitize-map.json
```

Fill in the real literals from your environment — internal addresses, your Slack
bot ID, hostnames, any organisation-specific webhook path. Then confirm the file
is actually ignored:

```bash
git check-ignore -v scripts/sanitize-map.json
```

If that prints nothing, **stop**. The file is not ignored, and you are one
`git add` away from publishing the exact list of sensitive values you just
wrote. The usual cause is a missing `.gitignore` — see the upload section above.

Then:

```bash
python3 scripts/sanitize_n8n_export.py raw-export.json \
        workflows/n8n/ai-soc-assistant/ai-soc-assistant.sanitized.json --report
python3 scripts/validate_json.py
python3 scripts/scan_sensitive_values.py
```

Full procedure: [`docs/workflow-lifecycle.md`](docs/workflow-lifecycle.md).

---

## Forking this repository

If you are publishing your own copy under a different account, replace the
maintainer identifiers first.

```bash
# macOS / BSD sed: use  sed -i ''  instead of  sed -i
grep -rl 'maryamoah' . --exclude-dir=.git --exclude=SETUP.md \
  | xargs sed -i 's|maryamoah|YOUR-USERNAME|g'

grep -rl 'techiesiwaamoah@gmail.com' . --exclude-dir=.git --exclude=SETUP.md \
  | xargs sed -i 's|techiesiwaamoah@gmail.com|your@email|g'
```

That covers CODEOWNERS, the README badge URLs, the issue templates, the four
JSON Schema `$id` values, both changelogs, `SECURITY.md` and
`CODE_OF_CONDUCT.md`. Verify with:

```bash
grep -rn 'maryamoah\|techiesiwaamoah' . --exclude-dir=.git --exclude=SETUP.md \
  || echo "Clean."
```

Then run the three validation scripts and follow the upload section above.
