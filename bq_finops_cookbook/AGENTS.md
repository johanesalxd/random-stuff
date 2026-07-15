# Agent Operating Guidelines

This directory is a prompt, SQL, and evidence project for the `bq-finops-analyst` Antigravity skill. It is not an application service.

## Runtime target

- Antigravity CLI
- Gemini 3.5 Flash with thinking set to **High**
- Workspace skill discovery from `.agents/skills/bq-finops-analyst/SKILL.md`
- `bq`/`gcloud` CLI authenticated with Application Default Credentials (ADC); read-only commands only

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
| `sample_results/` | Synthetic example reports, never current truth |

Do not duplicate detailed product rules across surfaces. Link to the canonical owner.

## Safety

1. All live GCP access is read-only: only `bq query` (SELECT), `bq show`, `bq ls`, `gcloud ... describe/list`.
2. Never run reservation, assignment, commitment, or dataset billing-model changes, and never emit runnable mutation commands or DDL.
3. Capacity/reservation/storage changes are written as recommendations with links to official docs, for the user to perform themselves.
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

## Sample-report rules

- Every sample starts with `**Synthetic sample:**`.
- Every numeric price has a dated assumptions block or is marked unverified.
- Final samples implement the complete report-heading contract.
- Samples must never violate current edition limits.
- Samples must never contain runnable mutation commands or DDL — recommendations link to official docs.

## Review gate

Before commit:

- Verify the named queries remain present and unique.
- Review every product-rule change against current official docs.
- Confirm no runtime file references MCP, and no mutation command or DDL is emitted.
- Treat a live BigQuery smoke as a separate approved gate; static review is not live proof.
