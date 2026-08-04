# bq_cross_cloud_lakehouse — moved

This demo now lives in its own repository:

**https://github.com/johanesalxd/bq-cross-cloud-lakehouse**

## What it is

A self-contained version of the Google Cloud Next '26 keynote demo *"Raw data to
forecasting in seconds with AI agents"*, restoring the AWS cross-cloud arm the
public codelab omits. BigLake Iceberg REST catalog federation with keyless OIDC
(`AssumeRoleWithWebIdentity`) and credential vending reads AWS S3/Glue Iceberg
tables directly from BigQuery, joins them with native BigQuery allergen
knowledge, and forecasts revenue with BQML `ARIMA_PLUS` over AWS-resident data.
A Conversational Analytics API agent published to Gemini Enterprise answers the
storyline in natural language. No Databricks and no Cross-Cloud Interconnect
required.

## History

The code was extracted at commit `23389ac` and squashed into a single initial
commit in the new repository. **The full 31-commit history remains here** and is
still browsable:

```bash
git log --oneline 23389ac -- bq_cross_cloud_lakehouse
git show 23389ac:bq_cross_cloud_lakehouse/README.md
```

The agent package was originally adapted from
[`bq_caapi_ge`](https://github.com/johanesalxd/random-stuff/tree/main/bq_caapi_ge),
which is still in this repository.
