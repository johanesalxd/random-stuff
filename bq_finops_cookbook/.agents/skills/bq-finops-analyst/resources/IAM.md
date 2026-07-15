# IAM and Privacy Matrix

The analyst authenticates with Application Default Credentials (ADC) and issues only read-only `bq`/`gcloud` commands. This skill never mutates cloud resources, so it only ever needs read access. The roles below are the minimum for the analysis to run; the running user brings their own ADC identity. Verify effective permissions in the target organization and record any gaps.

## Minimum read-only roles

All roles verified against Google Cloud documentation on 2026-07-15.

| Role | Grants | Evidence surfaces it unlocks |
|---|---|---|
| `roles/bigquery.jobUser` | `bigquery.jobs.create` | Running the read-only SELECT queries (minimal job-run role) |
| `roles/bigquery.resourceViewer` | `jobs.listAll`, `reservations.list`, `reservationAssignments.list`, `capacityCommitments.list` | `JOBS_BY_PROJECT`, `JOBS_TIMELINE_BY_PROJECT`, `RESERVATIONS*`, `ASSIGNMENTS*`, `CAPACITY_COMMITMENT_CHANGES*` |
| `roles/bigquery.metadataViewer` | `tables.get`, `tables.list` | `TABLES`, `COLUMNS`, `TABLE_STORAGE_BY_PROJECT`, `WRITE_API_TIMELINE_BY_PROJECT` |

Grant `roles/bigquery.resourceViewer` in the **reservation administration project** as well when reservations live in a separate project.

**Optional (only if official Slot Recommender output or dollar figures are requested):**

| Role | Grants | Purpose |
|---|---|---|
| `roles/bigquery.slotRecommenderViewer` | `recommender.bigqueryCapacityCommitmentsRecommendations.get/list` | `RECOMMENDATIONS_BY_PROJECT` + Slot Recommender/Estimator |
| `roles/billing.viewer` | `billing.accounts.getPricing` | Reveal hidden monthly cost values in recommendations |

## Never grant

These carry mutation permissions and must not be attached to the analysis identity: `roles/owner`, `roles/editor`, `roles/bigquery.admin`, `roles/bigquery.resourceAdmin`, `roles/bigquery.resourceEditor`, `roles/bigquery.dataEditor`, `roles/bigquery.dataOwner`, and any custom role containing `reservations.create/update/delete`, `reservationAssignments.create/delete`, `capacityCommitments.*`, or `tables.update/delete`.

## Evidence fallbacks

- Jobs unavailable → aggregate project-level evidence only.
- Reservation/commitment metadata denied → mark configuration unavailable; omit historical commitment analysis.
- Recommender denied → use Slot Estimator UI evidence supplied by the administrator.
- Storage/Write API denied → aggregate only accessible datasets; use Cloud Monitoring evidence supplied by the administrator.

## Privacy defaults

- Do not emit raw query SQL.
- Pseudonymize `user_email` and `job_id` in generated reports.
- Retain project, reservation, dataset, and table names only when needed for an actionable recommendation.
- Do not copy raw metadata rows into Markdown; aggregate first.
- State the analysis window and visibility scope so partial IAM is not mistaken for completeness.

## Evidence-gap format

```text
Status: BLOCKED
Surface: RESERVATIONS_BY_PROJECT
Scope: admin-project / us
Reason: Access denied
Impact: Current reservation baseline and autoscaling configuration not verified
Fallback: None available without administrator-supplied evidence
```

## Mutation boundary

The skill only issues read-only `bq`/`gcloud` commands. Even when the ADC principal happens to hold broader (write) permissions, the analyst must never run a resource-changing command. Reservation, assignment, commitment, and dataset storage-billing changes are recommendations the user performs themselves by following the linked official documentation.
