# IAM and Privacy Matrix

The analyst uses the active gcloud CLI account or configured service-account
impersonation for `bq` and `gcloud`. These credentials are distinct from
Application Default Credentials. Verify the effective principal and role scope;
never print an access token.

The skill issues only read-only operations. A principal having broader IAM does
not authorize the skill to mutate resources. For live execution, use a dedicated
analysis principal and verify its effective inherited and custom permissions do
not include BigQuery data or resource mutations. This is required because
terminal rules might not inspect the complete query payload. If that
effective-IAM check is unavailable or broader mutation access exists, stop
rather than claim an enforced read-only boundary.

## Minimum roles and binding scope

| Role | Required scope | Key permissions | Evidence surfaces |
|---|---|---|---|
| `roles/bigquery.jobUser` | Query project | `bigquery.jobs.create` | Creates the read-only metadata query jobs and determines their billing project |
| `roles/bigquery.resourceViewer` | Workload project | `bigquery.jobs.listAll` | Project-wide `JOBS_BY_PROJECT` and `JOBS_TIMELINE_BY_PROJECT` evidence |
| `roles/bigquery.resourceViewer` | Reservation administration project | Reservation, assignment, and capacity-commitment list permissions | `RESERVATIONS*`, `ASSIGNMENTS*`, and `CAPACITY_COMMITMENT_CHANGES*` |
| `roles/bigquery.metadataViewer` | Workload project | `tables.get`, `tables.list` | Project-level `TABLE_STORAGE_BY_PROJECT` and `WRITE_API_TIMELINE_BY_PROJECT` evidence |
| `roles/bigquery.metadataViewer` | Each required workload dataset | `tables.get`, `tables.list` | Dataset-scoped `TABLES` and `COLUMNS` audits only |

`bigquery.jobs.create` and `bigquery.jobs.listAll` are both required for the
project-wide jobs views used by this cookbook. If `jobs.listAll` is unavailable,
mark those surfaces `BLOCKED` or explicitly partial. Do not claim that a
project-wide aggregate remains available.

## Optional roles and APIs

| Role or service | Required scope | Purpose |
|---|---|---|
| Permissions for the recommender named by a generic `RECOMMENDATIONS_BY_PROJECT` row | Workload project | Generic active BigQuery recommendations; availability depends on each recommender's IAM |
| `roles/bigquery.slotRecommenderViewer` | Workload or reservation administration project required by the recommendation | Cost-optimized Slot Recommender/Estimator evidence for supported Enterprise/Enterprise Plus and on-demand-to-Enterprise scenarios |
| Recommender API and BigQuery Reservation API | Relevant project | Required for Slot Recommender console/API access |
| `roles/billing.viewer` | Billing account | Reveals otherwise hidden cost values when dollar analysis is requested |

Generic `INFORMATION_SCHEMA.RECOMMENDATIONS_BY_PROJECT` rows are not guaranteed
to include capacity guidance. Do not treat absence from that view as evidence
that Slot Recommender has no recommendation.

## Never grant for this analysis

Do not attach `roles/owner`, `roles/editor`, `roles/bigquery.admin`,
`roles/bigquery.resourceAdmin`, `roles/bigquery.resourceEditor`,
`roles/bigquery.dataEditor`, or `roles/bigquery.dataOwner` merely to make this
analysis run. Do not request custom roles containing reservation, assignment,
commitment, dataset, or table mutation permissions.

## Evidence gaps

- Project-wide jobs denied => mark job evidence `BLOCKED` or partial; do not
  invent an aggregate fallback. This also blocks the internal timeline-overlap
  bound probe and every dependent `JOBS_TIMELINE` query.
- Reservation/commitment metadata denied => mark current configuration
  unavailable and omit unsupported historical analysis.
- Slot Recommender denied or APIs disabled => record the precise gap and keep
  generic recommendations separate.
- Storage or Write API metadata denied => analyze only accessible datasets and
  state the visibility boundary.

Use this format:

```text
Status: BLOCKED
Surface: RESERVATIONS_BY_PROJECT
Scope: admin-project / us
Reason: Access denied
Impact: Current reservation maximum and scaling mode not verified
Fallback: None without administrator-supplied evidence
```

## Privacy defaults

- Do not emit raw query SQL.
- Pseudonymize `user_email`, `job_id`, and workload-derived table references
  with a fresh per-run salt that is never printed or persisted. Keep
  Google-provided normalized query hashes labelled separately.
- Retain approved project, reservation, and assignment identifiers when needed
  to describe configuration scope. Retain dataset/table names only for approved
  storage-inventory or dataset-audit recommendations. Query 4.2 references,
  Query 4.11 target resources, and Query 5.1 dataset/table identifiers remain
  fingerprinted; free-form recommendation descriptions are not persisted.
- Aggregate metadata before writing Markdown.
- State the analysis window and visibility scope so partial IAM is not mistaken
  for completeness.

## Mutation boundary

Only read-only `bq`/`gcloud` operations are permitted. Reservation, assignment,
commitment, and dataset storage-billing changes are recommendations the user
performs outside this skill by following official documentation.
