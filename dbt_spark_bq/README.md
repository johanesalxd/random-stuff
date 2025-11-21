# dbt + Spark on Dataproc → BigQuery Demo

This demo shows how to use **dbt-spark** with a **Dataproc cluster** as the execution engine, then write the final results to **BigQuery** using the Spark BigQuery connector.

## Architecture

```mermaid
graph LR
    A[Local dbt] -->|Thrift Protocol<br/>Port 10001| B[Dataproc Spark<br/>Thrift Server]
    B -->|Transformations| C[Hive Tables<br/>GCS Storage]
    C -->|Spark BigQuery<br/>Connector| D[BigQuery<br/>Tables]

    style A fill:#4285f4,stroke:#1967d2,stroke-width:2px,color:#fff
    style B fill:#34a853,stroke:#188038,stroke-width:2px,color:#fff
    style C fill:#fbbc04,stroke:#f29900,stroke-width:2px,color:#000
    style D fill:#ea4335,stroke:#c5221f,stroke-width:2px,color:#fff
```

### Data Flow

1. **Local dbt** connects to Dataproc via Thrift protocol (port 10001)
2. **Dataproc Spark** executes dbt transformations on the cluster
3. **Hive Tables** store transformed data in GCS-backed metastore
4. **Spark BigQuery Connector** writes final tables to BigQuery

## Why This Approach?

This architecture demonstrates:
- ✅ Using Spark as a distributed execution engine for dbt
- ✅ Leveraging Dataproc's managed Spark infrastructure
- ✅ Storing final analytics tables in BigQuery for BI/reporting
- ✅ Separating compute (Spark) from storage (BigQuery)

**Important Note:** dbt-spark cannot write directly to BigQuery. This demo uses a two-stage approach:
1. dbt-spark writes to Spark/Hive tables
2. Spark BigQuery connector copies tables to BigQuery

## Prerequisites

- **GCP Project** with billing enabled
- **gcloud CLI** installed and authenticated
- **Python 3.8+**
- **jaffle-shop-classic** repository cloned at `/Users/[username]/Developer/git/jaffle-shop-classic`

## Quick Start

### Option 1: Run the Jupyter Notebook

```bash
# Open the notebook
jupyter notebook dbt_spark_dataproc_demo.ipynb

# Execute cells sequentially
```

### Option 2: Manual Setup

#### 1. Set Configuration

```bash
export PROJECT_ID="johanesa-playground-326616"
export REGION="us-central1"
export ZONE="us-central1-a"
export CLUSTER_NAME="dbt-spark-demo-cluster"
export GCS_BUCKET="johanesa-dbt-spark-demo"
export BQ_DATASET="jaffle_shop_demo"
```

#### 2. Create GCS Bucket

```bash
gsutil mb -p $PROJECT_ID -l $REGION gs://$GCS_BUCKET
```

#### 3. Create Dataproc Cluster

```bash
gcloud dataproc clusters create $CLUSTER_NAME \
  --project=$PROJECT_ID \
  --region=$REGION \
  --zone=$ZONE \
  --single-node \
  --master-machine-type=n1-standard-4 \
  --master-boot-disk-size=100GB \
  --image-version=2.1-debian11 \
  --properties=hive:hive.metastore.warehouse.dir=gs://$GCS_BUCKET/hive-warehouse \
  --enable-component-gateway \
  --optional-components=JUPYTER \
  --metadata='SPARK_BQ_CONNECTOR_VERSION=0.43.1' \
  --initialization-actions=gs://goog-dataproc-initialization-actions-$REGION/connectors/connectors.sh
```

#### 4. Start Spark Thrift Server

```bash
gcloud compute ssh ${CLUSTER_NAME}-m \
  --project=$PROJECT_ID \
  --zone=$ZONE \
  --command="sudo /usr/lib/spark/sbin/start-thriftserver.sh \
    --master yarn \
    --deploy-mode client \
    --conf spark.sql.warehouse.dir=gs://$GCS_BUCKET/hive-warehouse \
    --conf spark.hadoop.hive.metastore.warehouse.dir=gs://$GCS_BUCKET/hive-warehouse"
```

#### 5. Install dbt-spark

```bash
pip install dbt-core dbt-spark[PyHive]
```

#### 6. Configure dbt Profile

Get the cluster master IP:
```bash
MASTER_IP=$(gcloud compute instances describe ${CLUSTER_NAME}-m \
  --project=$PROJECT_ID \
  --zone=$ZONE \
  --format='value(networkInterfaces[0].networkIP)')
```

Create `~/.dbt/profiles.yml`:
```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: spark
      method: thrift
      schema: default
      host: <MASTER_IP>
      port: 10001
      user: <YOUR_USERNAME>
      connect_timeout: 60
      connect_retries: 3
```

#### 7. Run dbt

```bash
cd /Users/[username]/Developer/git/jaffle-shop-classic

# Test connection
dbt debug

# Load seed data
dbt seed

# Run transformations
dbt run
```

#### 8. Create BigQuery Dataset

```bash
bq mk --project_id=$PROJECT_ID --location=US $BQ_DATASET
```

#### 9. Write to BigQuery

Create `write_to_bq.py`:
```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("Write to BigQuery") \
    .config("spark.sql.warehouse.dir", "gs://johanesa-dbt-spark-demo/hive-warehouse") \
    .enableHiveSupport() \
    .getOrCreate()

tables = ["customers", "orders"]

for table in tables:
    print(f"Writing {table} to BigQuery...")
    df = spark.table(f"default.{table}")
    df.write \
        .format("bigquery") \
        .option("table", f"johanesa-playground-326616.jaffle_shop_demo.{table}") \
        .option("temporaryGcsBucket", "johanesa-dbt-spark-demo") \
        .mode("overwrite") \
        .save()
    print(f"✓ {table} written to BigQuery")

spark.stop()
```

Submit the job:
```bash
gcloud dataproc jobs submit pyspark write_to_bq.py \
  --cluster=$CLUSTER_NAME \
  --project=$PROJECT_ID \
  --region=$REGION
```

#### 10. Verify Data

```bash
bq query --project_id=$PROJECT_ID --use_legacy_sql=false \
  'SELECT * FROM jaffle_shop_demo.customers LIMIT 5'

bq query --project_id=$PROJECT_ID --use_legacy_sql=false \
  'SELECT * FROM jaffle_shop_demo.orders LIMIT 5'
```

## Cleanup

Delete the Dataproc cluster to save costs:

```bash
gcloud dataproc clusters delete $CLUSTER_NAME \
  --project=$PROJECT_ID \
  --region=$REGION \
  --quiet
```

Optionally delete other resources:
```bash
# Delete GCS bucket
gsutil -m rm -r gs://$GCS_BUCKET

# Delete BigQuery dataset
bq rm -r -f -d $PROJECT_ID:$BQ_DATASET
```

## Resources Created

| Resource | Name | Location | Purpose |
|----------|------|----------|---------|
| Dataproc Cluster | `dbt-spark-demo-cluster` | us-central1 | Spark execution engine |
| GCS Bucket | `johanesa-dbt-spark-demo` | us-central1 | Hive metastore storage |
| BigQuery Dataset | `jaffle_shop_demo` | US (multi-region) | Final analytics tables |
| BigQuery Tables | `customers`, `orders` | US | Transformed data |

## Technical Details

### dbt-spark Connection

- **Method:** Thrift
- **Port:** 10001
- **Protocol:** JDBC/Thrift
- **Schema:** default (Hive database)

### Spark Configuration

- **Image Version:** 2.1-debian11
- **Spark Version:** 3.1.x
- **Hive Metastore:** GCS-backed
- **BigQuery Connector:** 0.43.1

### Data Pipeline

1. **Seed Data:** CSV files → Spark tables
2. **Staging Models:** Raw tables → Staging tables (views)
3. **Final Models:** Staging tables → Final tables (materialized)
4. **BigQuery Export:** Spark tables → BigQuery tables

## Troubleshooting

### Connection Issues

If `dbt debug` fails:
```bash
# Check Thrift server is running
gcloud compute ssh ${CLUSTER_NAME}-m \
  --project=$PROJECT_ID \
  --zone=$ZONE \
  --command="netstat -tuln | grep 10001"

# Restart Thrift server if needed
gcloud compute ssh ${CLUSTER_NAME}-m \
  --project=$PROJECT_ID \
  --zone=$ZONE \
  --command="sudo /usr/lib/spark/sbin/stop-thriftserver.sh && \
    sudo /usr/lib/spark/sbin/start-thriftserver.sh --master yarn"
```

### BigQuery Write Errors

If Spark BigQuery connector fails:
```bash
# Verify connector is installed
gcloud compute ssh ${CLUSTER_NAME}-m \
  --project=$PROJECT_ID \
  --zone=$ZONE \
  --command="ls -la /usr/lib/spark/jars/ | grep bigquery"

# Check GCS bucket permissions
gsutil iam get gs://$GCS_BUCKET
```

### Performance Tuning

For larger datasets:
```yaml
# In profiles.yml, add:
server_side_parameters:
  "spark.driver.memory": "4g"
  "spark.executor.memory": "4g"
  "spark.sql.shuffle.partitions": "200"
```

## Cost Estimation

Approximate costs for running this demo (1 hour):

- **Dataproc Cluster:** ~$0.50/hour (n1-standard-4)
- **GCS Storage:** ~$0.02/GB/month
- **BigQuery Storage:** ~$0.02/GB/month
- **BigQuery Queries:** Free (first 1TB/month)

**Total:** ~$0.50 for a 1-hour demo

## References

- [dbt-spark Documentation](https://docs.getdbt.com/docs/core/connect-data-platform/spark-setup)
- [Dataproc Documentation](https://cloud.google.com/dataproc/docs)
- [Spark BigQuery Connector](https://github.com/GoogleCloudDataproc/spark-bigquery-connector)
- [jaffle-shop-classic](https://github.com/dbt-labs/jaffle-shop-classic)

## License

This demo is provided as-is for educational purposes.
