# Agent Operating Guidelines

This directory is a prompt, SQL, evidence, and validation project for the `bq-finops-analyst` Antigravity skill. It is not an application service.

## Runtime target

- Antigravity CLI
- Gemini 3.5 Flash with thinking set to **High**
- Workspace skill discovery from `.agents/skills/bq-finops-analyst/SKILL.md`
- BigQuery MCP first; read-only `bq` fallback only

Do not optimize this project for another runtime at the expense of Antigravity/Flash behavior.

## Canonical ownership

| Surface | Owns |
|---|---|
| `README.md` | Human onboarding and high-level safety |
| `.agents/skills/bq-finops-analyst/SKILL.md` | Trigger, inputs, workflow, guardrails, outputs |
| `resources/finops_agent.md` | Query corpus, calculations, decision/report templates |
| `resources/execution_manifest.json` | Compact query order, applicability, fallback, target report |
| `resources/claim_matrix.json` | Dated volatile product/price claims |
| `resources/REFERENCES.md` | Official source catalogue |
| `resources/IAM.md` | Staged access and privacy model |
| `sample_results/` | Synthetic contract fixtures, never current truth |
| `scripts/` and `tests/` | Deterministic regression protection |

Do not duplicate detailed product rules across surfaces. Link to the canonical owner.

## Safety

1. All live GCP analysis is read-only.
2. Never execute reservation, assignment, commitment, or dataset billing-model changes.
3. A generated mutation command must be labelled `PROPOSAL_NONDESTRUCTIVE` or `PROPOSAL_DESTRUCTIVE` and require explicit administrator approval.
4. Do not commit credentials, tokens, project secrets, raw customer query text, or identifiable user emails.
5. Missing evidence must remain visible; do not fabricate or silently omit it.

## SQL conventions

- BigQuery GoogleSQL only.
- Uppercase keywords; two-space indentation.
- Keep project/location placeholders explicit.
- Use `(statement_type != 'SCRIPT' OR statement_type IS NULL)` where script-parent double counting applies.
- Use `SAFE_DIVIDE` or an equivalent zero guard.
- Keep slot-seconds, slot-hours, average slots, baseline slots, scaled slots, and billed slots distinct.
- Add an official source URL above each complex query.
- Document required IAM, scope, retention, and fallback in the query ledger/manifest.

## TDD workflow

For validator or decision behavior changes:

1. Write one failing `unittest`.
2. Run the targeted test and confirm the expected failure.
3. Implement the minimum change.
4. Run the targeted test until green.
5. Run the complete suite.

Commands:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_cookbook.py all
python3 scripts/validate_cookbook.py inventory
git diff --check
```

## Sample-report rules

- Every sample starts with `**Synthetic sample:**`.
- Every numeric price has a dated assumptions block or is marked unverified.
- Final samples implement the complete report-heading contract.
- Samples must never violate current edition limits.
- Samples are mutation-tested because models copy examples aggressively.

## Review gate

Before commit:

- Verify all 25 named queries remain present and unique.
- Verify all 14 samples pass contract checks.
- Review every product-rule change against current official docs.
- Run an independent reviewer over the final diff.
- Treat a live BigQuery smoke as a separate approved gate; offline checks are not live proof.
