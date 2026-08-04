# Repository setup

One-time steps to run **before** the first push. The repository ships with
placeholder identifiers so it is obvious what has not been personalised yet.

## 1. Replace the placeholders

`your-org` appears in 14 files: CODEOWNERS, issue templates, schema `$id` URLs,
changelog release links, and a few documentation links.

```bash
# macOS / BSD sed: use  sed -i ''  instead of  sed -i
grep -rl 'your-org' . --exclude-dir=.git \
  | xargs sed -i 's|your-org|YOUR-GITHUB-USERNAME|g'
```

Then set the security contact, which `SECURITY.md` and `CODE_OF_CONDUCT.md`
both point at:

```bash
sed -i 's|techiesiwaamoah@gmail.com|your.real@email|' .github/CODEOWNERS
```

**CODEOWNERS caveat.** It ships referencing a GitHub *team*
(`@maryamoah/soc-automation`). Teams only exist inside organisations. On a
personal account, replace the team with your username:

```bash
sed -i 's|@maryamoah/soc-automation|@YOUR-GITHUB-USERNAME|g' \
  .github/CODEOWNERS
```

An unresolvable CODEOWNERS entry is silently ignored by GitHub, so this will not
break anything — it just will not do anything either.

## 2. Verify

```bash
grep -rn 'maryamoah\|techiesiwaamoah@gmail.com' . --exclude-dir=.git || \
  echo "No placeholders remain."

python3 scripts/validate_json.py
python3 scripts/validate_examples.py
python3 scripts/scan_sensitive_values.py
```

All three must pass. They also run in CI on every push.

## 3. Create your sanitizer map

Only needed if you will re-export the workflow from your own n8n instance.

```bash
cp scripts/sanitize-map.example.json scripts/sanitize-map.json
$EDITOR scripts/sanitize-map.json
```

Fill in the real literals from your environment — internal addresses, your Slack
bot ID, hostnames, any organisation-specific webhook path. The file is
git-ignored **because its keys are the sensitive values themselves**. Confirm:

```bash
git check-ignore -v scripts/sanitize-map.json
```

If that prints nothing, stop: the file is not ignored and you are one `git add`
away from publishing the list you just wrote.

## 4. First push

```bash
git init -b main
git add .
git status                      # read this properly before committing
git commit -m "feat: initial release — AI SOC Assistant n8n workflow"
git remote add origin git@github.com:maryamoah/soc-automation-playbooks.git
git push -u origin main
```

Read `git status` before the first commit. It is the last cheap moment to notice
a stray `.env`, a raw export, or a screenshot you meant to redact.

## 5. Repository settings

| Setting | Value |
|---|---|
| Description | AI-assisted SOC triage with n8n and a locally hosted LLM. Sanitized, importable workflow exports with full documentation. |
| Topics | `soc`, `security-automation`, `soar`, `n8n`, `ollama`, `wazuh`, `slack`, `llm`, `blue-team`, `incident-response`, `threat-detection` |
| Wikis / Projects | Off — the documentation lives in the repository |
| Issues | On |

Under *Settings → Code security*, enable **secret scanning** and **push
protection**. Push protection blocks a commit containing a recognised token
*before* it reaches GitHub, which is the only control here that acts before
exposure rather than after it. This repository's own scanner runs after the
push; treat them as complementary.

Under *Settings → Actions → General*, set workflow permissions to **read-only**.
Nothing in this repository needs write access to itself.

## 6. What CI will do on the first run

| Workflow | Expected |
|---|---|
| JSON validation | Pass |
| Secret scan | Pass |
| Python validation | Pass |
| Markdown lint | Link check passes; markdownlint is advisory (`continue-on-error: true`) and will likely report cosmetic line-length findings |

Markdown lint is deliberately non-blocking. A style nit should not turn a
contributor's documentation fix into a red build.

## 7. Optional: branch protection

Useful if others will contribute; unnecessary friction if it is only you.

*Settings → Branches → Add rule* on `main`: require pull requests, and require
the JSON validation, Secret scan and Python validation checks to pass. Leave
Markdown lint out — it is advisory by design.
