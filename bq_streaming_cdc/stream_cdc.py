import logging
import time
from typing import Any, Dict, List, Type

from google.cloud import bigquery
from google.cloud import bigquery_storage_v1
from google.cloud.bigquery_storage_v1 import types
from google.protobuf import descriptor_pb2, descriptor_pool, message, message_factory

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class CDCSchemaFactory:
    """Handles the dynamic generation of Protobuf classes for BigQuery CDC."""

    @staticmethod
    def create_row_class() -> Type[message.Message]:
        """Dynamically creates a Protobuf class for our table + CDC fields."""
        desc = descriptor_pb2.DescriptorProto()
        desc.name = "CDCRow"

        # Define fields
        # Note: These must match the target table schema and CDC requirements
        fields = [
            ("id", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT64),
            ("name", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
            ("_CHANGE_TYPE", 3, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
            (
                "_CHANGE_SEQUENCE_NUMBER",
                4,
                descriptor_pb2.FieldDescriptorProto.TYPE_INT64,
            ),
        ]

        for name, number, type_enum in fields:
            field = desc.field.add()
            field.name = name
            field.number = number
            field.type = type_enum

        # Create a pool and add the file descriptor
        pool = descriptor_pool.DescriptorPool()
        file_desc = descriptor_pb2.FileDescriptorProto()
        file_desc.name = "cdc_demo.proto"
        file_desc.package = "cdc_demo"
        file_desc.message_type.add().MergeFrom(desc)

        pool.Add(file_desc)

        # Get the generated class
        return message_factory.GetMessageClass(
            pool.FindMessageTypeByName("cdc_demo.CDCRow")
        )


class BigQueryCDCWriter:
    """Wraps the BigQuery Storage Write API for CDC operations."""

    def __init__(self, project_id: str, dataset_id: str, table_id: str):
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.client = bigquery_storage_v1.BigQueryWriteClient()
        self.bq_client = bigquery.Client()
        self.parent = self.client.table_path(project_id, dataset_id, table_id)
        self.stream_name = f"{self.parent}/streams/_default"
        self.row_class = CDCSchemaFactory.create_row_class()

    def _create_proto_row(self, data: Dict[str, Any]) -> message.Message:
        """Converts a dictionary to a Protobuf message instance."""
        row = self.row_class()
        for key, value in data.items():
            if hasattr(row, key):
                setattr(row, key, value)
            else:
                logger.warning(f"Field '{key}' not found in Protobuf schema.")
        return row

    def append_rows(self, row_dicts: List[Dict[str, Any]]) -> None:
        """
        Appends a list of row dictionaries to BigQuery.

        Args:
            row_dicts: List of dictionaries containing row data and CDC metadata.
        """
        if not row_dicts:
            logger.info("No rows to append.")
            return

        # 1. Serialize rows
        proto_rows = types.ProtoRows()
        for data in row_dicts:
            row_msg = self._create_proto_row(data)
            proto_rows.serialized_rows.append(row_msg.SerializeToString())

        # 2. Construct request
        request = types.AppendRowsRequest()
        request.write_stream = self.stream_name

        # 3. Attach Schema (Required for the first request in the stream)
        # We attach it to every batch here for simplicity in this stateless demo
        proto_data = types.AppendRowsRequest.ProtoData()
        proto_data.writer_schema = types.ProtoSchema()

        descriptor_proto = descriptor_pb2.DescriptorProto()
        self.row_class.DESCRIPTOR.CopyToProto(descriptor_proto)

        proto_data.writer_schema.proto_descriptor = descriptor_proto
        proto_data.rows = proto_rows
        request.proto_rows = proto_data

        # 4. Send Request
        # AppendRows is a bidirectional streaming RPC.
        # We send a single request iterator and consume the response iterator.
        requests = [request]
        response_stream = self.client.append_rows(iter(requests))

        # 5. Handle Response
        try:
            for response in response_stream:
                if response.error.code:
                    logger.error(f"Append Error: {response.error}")
                else:
                    logger.info(f"Successfully appended {len(row_dicts)} rows.")
                    if response.append_result.offset is not None:
                        logger.debug(f"Offset: {response.append_result.offset.value}")
        except Exception as e:
            logger.exception("Failed to append rows.")

    def verify_table_content(self):
        """Forces a fresh read of the table and prints the current state."""
        table_ref = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
        logger.info(f"Verifying content of {table_ref}...")

        # Query content
        query_sql = f"SELECT * FROM `{table_ref}` ORDER BY id"
        query_job = self.bq_client.query(query_sql)
        results = list(query_job.result())

        if not results:
            logger.info("Table is EMPTY.")
        else:
            logger.info("Table Content:")
            print("-" * 30)
            print(f"{'ID':<5} | {'Name':<20}")
            print("-" * 30)
            for row in results:
                print(f"{row.id:<5} | {row.name:<20}")
            print("-" * 30)


def main():
    PROJECT_ID = "johanesa-playground-326616"
    DATASET_ID = "demo_dataset"
    TABLE_ID = "cdc_demo"

    writer = BigQueryCDCWriter(PROJECT_ID, DATASET_ID, TABLE_ID)

    # Define the sequence of CDC events
    # _CHANGE_SEQUENCE_NUMBER ensures correct ordering even if they arrive out of order
    cdc_events = [
        {
            "id": 1,
            "name": "Alice",
            "_CHANGE_TYPE": "UPSERT",
            "_CHANGE_SEQUENCE_NUMBER": 1,
        },
        {
            "id": 1,
            "name": "Alice",
            "_CHANGE_TYPE": "DELETE",
            "_CHANGE_SEQUENCE_NUMBER": 2,
        },
        {
            "id": 1,
            "name": "Alice Restored",
            "_CHANGE_TYPE": "UPSERT",
            "_CHANGE_SEQUENCE_NUMBER": 3,
        },
        {
            "id": 2,
            "name": "Bob",
            "_CHANGE_TYPE": "UPSERT",
            "_CHANGE_SEQUENCE_NUMBER": 4,
        },
    ]

    logger.info("Starting CDC streaming demo...")
    writer.append_rows(cdc_events)

    # Wait briefly for ingestion to propagate (CDC application is usually near-instant but API latency exists)
    time.sleep(2)

    writer.verify_table_content()
    logger.info("Demo complete.")


if __name__ == "__main__":
    main()
