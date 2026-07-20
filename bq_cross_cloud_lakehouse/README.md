# Cross-Cloud Lakehouse: query AWS Glue Iceberg from BigQuery

A minimal, low-cost demo of Google Cloud's **cross-cloud Lakehouse** (BigLake
Iceberg REST catalog, *Preview*): register an Apache Iceberg table that lives in
**AWS Glue + S3**, then query it live from **BigQuery** — no data copy.

Based on the official docs:
- https://docs.cloud.google.com/lakehouse/docs/set-up-cross-cloud-lakehouse-aws-glue
- https://docs.cloud.google.com/lakehouse/docs/use-cross-cloud-lakehouse

## Architecture

```
AWS us-east-1                              GCP us-east4
┌───────────────────────────┐             ┌─────────────────────────────┐
│ S3 (Iceberg data)         │  metadata   │ BigLake federated catalog   │
│ Glue Data Catalog (table) │◀────refresh─│ (OIDC web-identity to AWS)  │
│ IAM role (AssumeRole      │  + reads    │            ▼                │
│  WithWebIdentity)         │             │ BigQuery SQL (4-part path)  │
└───────────────────────────┘             └─────────────────────────────┘
```

Auth is OIDC: GCP's BigLake service account assumes an AWS IAM role via
`sts:AssumeRoleWithWebIdentity` — there are **no long-lived AWS keys** stored in
GCP.

## Cost

Essentially free for a small demo: Glue Data Catalog free tier, a few KB in S3,
tiny public-internet egress, and Athena (~$5/TB scanned → fractions of a cent).
Tear everything down with the `90_teardown.sh` scripts afterward.

## Security / this is a public repo

- **Never committed:** `config.local.env` (real IDs) and `.env` are git-ignored.
- AWS credentials live only in `~/.aws/` (via `aws configure`) — never in the repo.
- Committed files use placeholders (`config.example.env`) and templates
  (`aws/policies/*.template.json`, rendered into the git-ignored `.generated/`).

## Prerequisites

- `gcloud` (with `alpha` component), `bq`, and AWS CLI v2.
- A GCP project allowlisted for the cross-cloud Lakehouse Preview, with
  `roles/biglake.admin` (+ `roles/bigquery.jobUser`, `roles/bigquery.dataViewer`,
  `roles/biglake.viewer` to query).
- An AWS account + an IAM identity with rights to create S3/Glue/Athena/IAM.

## Setup

```bash
# Enable the required Google Cloud APIs (once per project).
gcloud services enable biglake.googleapis.com bigquery.googleapis.com

cp config.example.env config.local.env   # then edit with your real values
aws configure                            # stores keys in ~/.aws, region us-east-1
```

## Run order

| Step | Script | What it does |
|------|--------|--------------|
| 1 | `aws/01_verify.sh` | Confirm CLI auth + account matches config |
| 2 | `aws/10_s3_glue.sh` | Create S3 bucket + Glue database |
| 3 | `aws/11_iceberg_table_athena.sh` | Create + populate a small Iceberg table |
| 4 | `aws/20_iam_role.sh` | Create IAM role (placeholder trust) + scoped policy |
| 5 | `gcp/10_create_federated_catalog.sh` | Create catalog; prints BigLake SA ID |
| 6 | `aws/30_update_trust_policy.sh <SA_ID>` | Finalize AWS trust policy |
| 7 | `gcp/20_enable_refresh.sh` | Enable 300s metadata refresh (after propagation) |
| 8 | `gcp/30_verify.sh` | Confirm refresh OK + namespaces synced |
| 9 | `gcp/40_query.sh` | Query the AWS table from BigQuery |

## Teardown (after the demo)

```bash
./gcp/90_teardown.sh
./aws/90_teardown.sh   # also prints commands to delete the demo IAM user
```

See `docs/runbook.md` for the full narrative and demo talk-track.
