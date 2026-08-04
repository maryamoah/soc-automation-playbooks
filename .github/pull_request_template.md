## What does this change?

<!-- One or two sentences. Link the issue if there is one. -->

Closes #

## Type of change

- [ ] New workflow
- [ ] Workflow fix or improvement
- [ ] Prompt change
- [ ] Documentation
- [ ] Tooling / CI
- [ ] Security fix

## Accuracy

This repository documents **what runs, not what was intended**.

- [ ] Nothing planned is described as implemented
- [ ] Status tables updated in **both** the root README and
      `workflows/<platform>/README.md`, if status changed
- [ ] Any defect, unwired branch or missing error path is documented rather than
      quietly omitted
- [ ] Limitations sections updated if this change fixes or introduces one

## Data safety

- [ ] No credentials, tokens, keys, credential IDs or instance IDs
- [ ] No Slack channel, user, team or app IDs
- [ ] No internal domains, hostnames or RFC 1918 addressing
- [ ] No real security events or real IOCs
- [ ] No employer, university or customer names
- [ ] Examples are synthetic and use RFC 5737 documentation addresses
- [ ] Any screenshot follows `assets/screenshots/README.md` (painted redaction,
      not blurred; metadata stripped)

## Validation

```bash
python3 scripts/validate_json.py
python3 scripts/validate_examples.py
python3 scripts/scan_sensitive_values.py
```

- [ ] All three pass locally

## For workflow changes

- [ ] Export sanitized with `scripts/sanitize_n8n_export.py`
- [ ] Sanitized export re-imports into a clean n8n instance and runs after
      credentials are reassigned
- [ ] Node reference updated
- [ ] Diagrams updated if the topology changed
- [ ] Workflow CHANGELOG updated

## For prompt changes

- [ ] Diffed the prompt and checked nothing was removed by accident — these are
      mostly negative constraints and it is easy to delete a guard rail
- [ ] Full six-case test set re-run
- [ ] Cases 2 and 3 specifically re-checked (over-claiming, insufficient evidence)
- [ ] Model tested with: <!-- e.g. qwen3:14b -->

## Anything reviewers should look at closely?

<!-- Trade-offs, things you were unsure about, things you could not test. -->
