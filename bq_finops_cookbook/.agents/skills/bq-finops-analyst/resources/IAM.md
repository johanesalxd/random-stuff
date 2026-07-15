# IAM and Privacy Matrix

The analyst must use the smallest evidence surface available. Role names are starting points, not guarantees; verify permissions in the target organization and record gaps.

## Staged access

| Stage | Evidence | Typical permission family | Sensitive fields | Fallback |
|---|---|---|---|---|
| Workload jobs | `JOBS_BY_PROJECT`, `JOBS_TIMELINE_BY_PROJECT` | `bigquery.jobs.listAll` / BigQuery Resource Viewer | User email, job ID, optional query text | Aggregate project-level evidence only |
| Reservation config | `RESERVATIONS*`, `ASSIGNMENTS*` | BigQuery reservation metadata permissions in admin project | Assignee IDs | Mark configuration unavailable |
| Commitments | `CAPACITY_COMMITMENT_CHANGES*` | Reservation/commitment metadata permissions | Commercial configuration | Omit historical commitment analysis |
| Recommendations | `RECOMMENDATIONS*` or Recommender API | Recommender list/get permissions | Cost impact and target resources | Use Slot Estimator UI evidence supplied by administrator |
| Storage | `TABLE_STORAGE*`, `TABLES` | BigQuery metadata/list permissions | Dataset/table names | Aggregate only accessible datasets |
| Write API | `WRITE_API_TIMELINE*` | BigQuery resource metadata permissions | Table and error metadata | Cloud Monitoring evidence supplied by administrator |

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

No role granted to this analyst is permission to mutate. Even when the authenticated principal has broader permissions, the skill remains read-only. Reservation, assignment, commitment, and dataset billing changes are proposals for a separate administrator-controlled workflow.
