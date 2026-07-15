# Agent Operating Guidelines

This directory is a prompt, SQL, and evidence project for the `bq-finops-analyst` Antigravity skill. It is not an application service.

## Runtime target

- Antigravity CLI
- Gemini 3.5 Flash selected through `/model`
- Workspace skill discovery from `.agents/skills/bq-finops-analyst/SKILL.md`
- `bq`/`gcloud` CLI with active or impersonated gcloud credentials for live
  data; read-only operations only

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
| `resources/HISTORICAL_PARITY.md` | Disposition of historical queries and retired behavior |
| `sample_results/` | Synthetic example reports, never current truth |

Do not duplicate detailed product rules across surfaces. Link to the canonical owner.

## Safety

1. Repository maintenance grounds changed claims with Google Developer
   Knowledge MCP, Context7, or first-party web retrieval. This is a review
   requirement, not a runtime dependency of the skill. Live GCP data access
   uses only read-only `bq`/`gcloud`, never BigQuery MCP.
2. Bind every query job to the explicit query project, BigQuery location, and
   GoogleSQL mode. Prohibit DDL, DML, destinations, append/replace options, and
   write dispositions.
3. Never run reservation, assignment, commitment, or dataset billing-model
   changes, and never emit runnable mutation commands or DDL.
4. Capacity/reservation/storage changes are recommendations with official-doc
   links for the user to perform.
5. Do not commit credentials, tokens, project secrets, raw customer query text,
   or identifiable user emails.
6. Missing evidence remains `GAP` or `BLOCKED`; never fabricate or silently omit
   it.

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

Before commit, run three independent read-only reviewer lanes. Each returns:

| Lane | PASS/GAP | Evidence reviewed | Findings | Blocking impact |
|---|---|---|---|---|

- **Product-rule lane:** Retrieve every changed or used volatile claim from
  first-party Google Cloud or Antigravity pages, preferring Google Developer
  Knowledge MCP, then Context7 or official-web retrieval. Confirm claim value,
  retrieval date, location/edition/CLI/preview scope, and `claim_matrix.json`
  reconciliation.
- **SQL lane:** Confirm all 25 query IDs are unique and manifest-aligned. Check
  official view schemas, fields, IAM, retention, project/location qualification,
  fallbacks, null/zero guards, units, privacy, and read-only SQL/flags.
- **Report lane:** Confirm seven outputs, required query statuses, final heading
  order, evidence labels, metric/assumption consistency, synthetic marking, and
  the absence of raw principals or executable mutations.

The main agent reconciles all lanes. An unresolved safety, source, query-contract,
or strategy-changing `GAP` blocks completion. Repository reviews refresh touched
claims plus cross-file contracts; every live analysis refreshes every volatile
claim it uses. A live BigQuery smoke remains a separate approved gate; static
review is not live proof.
