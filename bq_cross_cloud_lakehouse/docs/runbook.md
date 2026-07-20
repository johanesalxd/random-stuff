# Runbook — Cross-Cloud Lakehouse demo

End-to-end steps, timing, and the demo talk-track. All commands assume you are in
the `bq_cross_cloud_lakehouse/` directory and have created `config.local.env`.

## Phase 1 — Tooling + guardrails (done during prep)

- Install AWS CLI v2, `aws configure` (region `us-east-1`, output `json`).
- `./aws/01_verify.sh` → confirms account + region.
- AWS guardrails (console, as root): root MFA, a **Zero-spend** budget, a **$1**
  monthly budget with email alerts, and **Cost Anomaly Detection** enabled.
- GCP guardrails: a budget + alert on the billing account; confirm Preview access
  with `gcloud alpha biglake iceberg catalogs list --project=<PROJECT>`.

## Phase 2 — AWS Iceberg dataset

```bash
./aws/10_s3_glue.sh
./aws/11_iceberg_table_athena.sh
./aws/20_iam_role.sh
```

## Phase 3 — Federation

```bash
./gcp/10_create_federated_catalog.sh          # note the printed BigLake SA ID
./aws/30_update_trust_policy.sh <BIGLAKE_SA_ID>
sleep 120                                      # let IAM propagate
./gcp/20_enable_refresh.sh
./gcp/30_verify.sh                             # expect namespace: demo_db
```

## Phase 4 — Query + talk-track

```bash
./gcp/40_query.sh
```

**Talk-track (~5 min):**
1. "This Iceberg table physically lives in **AWS** — S3 for data, Glue for the
   catalog." (show the Glue table / S3 prefix in the AWS console).
2. "We registered it once in a **BigLake federated catalog**. Auth is OIDC —
   BigQuery assumes an AWS IAM role; no AWS keys are stored in Google Cloud."
3. Run `gcp/40_query.sh` — "Standard BigQuery SQL, 4-part path
   `project.catalog.namespace.table`, querying AWS data live, **no copy**."
4. Show the aggregate query — "Metadata is cached and refreshed every 5 minutes;
   queries read S3 directly with short-lived vended credentials."

## Phase 5 — Teardown (right after the demo)

```bash
./gcp/90_teardown.sh
./aws/90_teardown.sh
```

Then, to fully stop spend / rotate the demo credential:
- Delete the demo IAM user (commands printed by `aws/90_teardown.sh`).
- Keep the AWS budget + anomaly alerts running a few days as a backstop.
- Confirm `$0` in AWS Cost Explorer the next day.

## Troubleshooting

- **Catalog refresh fails right after creation** — expected while IAM propagates;
  that's why refresh is enabled only in Phase 3 after `sleep`.
- **`AccessDenied` on refresh** — recheck the trust policy `aud`/`sub` both equal
  the BigLake SA ID, and that the permissions policy covers the bucket + Glue.
- **No namespaces listed** — confirm the Glue database/table exist in the same
  `AWS_REGION` and that `--glue-warehouse` is the 12-digit account ID.
- Preview support: biglake-help@google.com
