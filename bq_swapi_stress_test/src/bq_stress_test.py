"""BigQuery Storage Write API stress test pipeline.

Generates synthetic e-commerce transaction data to saturate BigQuery
ingestion bandwidth. Target: 300 MB/s for 10 minutes (180 GB total).
"""

import argparse
import json
import logging
import time
import uuid

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.utils.timestamp import Timestamp


# E-commerce data constants for realistic transactions
PRODUCTS = [
    "Wireless Bluetooth Headphones",
    "USB-C Charging Cable",
    "Laptop Stand Aluminum",
    "Mechanical Keyboard RGB",
    "Ergonomic Mouse Wireless",
    "4K Webcam Pro",
    "Portable SSD 1TB",
    "Phone Case Protective",
    "Screen Protector Tempered Glass",
    "Power Bank 20000mAh",
]

CATEGORIES = [
    "Electronics",
    "Accessories",
    "Computing",
    "Peripherals",
    "Storage",
    "Mobile",
    "Audio",
]

PAYMENT_METHODS = [
    "credit_card",
    "debit_card",
    "paypal",
    "apple_pay",
    "google_pay",
]

# BigQuery table schema
TABLE_SCHEMA = {
    "fields": [
        {"name": "transaction_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "customer_id", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "customer_email", "type": "STRING", "mode": "REQUIRED"},
        {"name": "order_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "product_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "product_name", "type": "STRING", "mode": "REQUIRED"},
        {"name": "product_category", "type": "STRING", "mode": "REQUIRED"},
        {"name": "quantity", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "unit_price", "type": "FLOAT", "mode": "REQUIRED"},
        {"name": "total_amount", "type": "FLOAT", "mode": "REQUIRED"},
        {"name": "currency", "type": "STRING", "mode": "REQUIRED"},
        {"name": "payment_method", "type": "STRING", "mode": "REQUIRED"},
        {"name": "shipping_address", "type": "STRING", "mode": "REQUIRED"},
        {"name": "order_status", "type": "STRING", "mode": "REQUIRED"},
    ]
}


def generate_uuid_from_int(n: int) -> str:
    """Generate deterministic UUID from integer for reproducibility."""
    return str(uuid.UUID(int=n % (2**128)))


def generate_address_blob(element: int) -> str:
    """Generate a ~4.7KB shipping address JSON blob.

    This is the "fat" field that brings row size to ~5KB total.
    Uses deterministic generation for reproducibility.
    """
    street_num = (element % 9999) + 1
    street_names = [
        "Main Street",
        "Oak Avenue",
        "Maple Drive",
        "Cedar Lane",
        "Pine Road",
        "Elm Boulevard",
        "Washington Street",
        "Park Avenue",
    ]
    cities = [
        "Singapore",
        "Kuala Lumpur",
        "Jakarta",
        "Bangkok",
        "Manila",
        "Ho Chi Minh City",
    ]

    street = street_names[element % len(street_names)]
    city = cities[element % len(cities)]
    postal_code = f"{(element % 999999):06d}"

    # Create nested address structure
    address = {
        "street_address": f"{street_num} {street}",
        "unit": f"#{(element % 99) + 1:02d}-{(element % 999) + 1:03d}",
        "building": f"Block {(element % 50) + 1}",
        "city": city,
        "state": "Southeast Asia",
        "postal_code": postal_code,
        "country": "SG",
        "coordinates": {
            "latitude": 1.3521 + (element % 1000) / 10000.0,
            "longitude": 103.8198 + (element % 1000) / 10000.0,
        },
        "delivery_instructions": (
            "Please call upon arrival. Leave package with security if no answer. "
            "Building has restricted access after 10 PM. Contact number: +65-"
            f"{(element % 90000000) + 10000000:08d}. "
            "Additional notes: This is a residential unit. Please ring doorbell twice. "
            "If delivering during office hours, recipient may be at work. "
            "Alternative contact available upon request."
        ),
        # Padding to reach ~4.7KB total
        "metadata": {f"field_{i}": f"value_{element}_{i}" * 20 for i in range(50)},
    }

    return json.dumps(address)


def generate_transaction(element) -> dict:
    """Generate a ~5KB e-commerce transaction row.

    Args:
        element: Schema-aware element from GenerateSequence (has .value field).

    Returns:
        Dictionary representing a transaction row.
    """
    # Extract value from schema-aware element (Beam 2.50+)
    seq_num = element.value if hasattr(element, "value") else element

    # Deterministic values based on element for reproducibility
    customer_id = seq_num % 1_000_000
    product_idx = seq_num % len(PRODUCTS)
    category_idx = seq_num % len(CATEGORIES)
    payment_idx = seq_num % len(PAYMENT_METHODS)

    quantity = (seq_num % 5) + 1
    unit_price = 10.0 + (seq_num % 500)

    return {
        "transaction_id": f"{seq_num:012d}-{generate_uuid_from_int(seq_num)}",
        "customer_id": customer_id,
        "customer_email": f"user{customer_id}@example.com",
        "order_timestamp": Timestamp.of(time.time()),
        "product_id": f"PROD-{product_idx:06d}",
        "product_name": PRODUCTS[product_idx],
        "product_category": CATEGORIES[category_idx],
        "quantity": quantity,
        "unit_price": unit_price,
        "total_amount": quantity * unit_price,
        "currency": "USD",
        "payment_method": PAYMENT_METHODS[payment_idx],
        "shipping_address": generate_address_blob(seq_num),
        "order_status": "confirmed",
    }


def run():
    """Execute the stress test pipeline."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output_table",
        required=True,
        help="BigQuery output table (project:dataset.table)",
    )

    known_args, pipeline_args = parser.parse_known_args()

    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(StandardOptions).streaming = True

    logging.info(
        "Starting stress test pipeline. Target: 300 MB/s for 10 minutes (180 GB total)"
    )

    with beam.Pipeline(options=pipeline_options) as p:
        (
            p
            | "GenerateSequence"
            >> beam.io.GenerateSequence(
                start=0,
                # Unbounded - will be cancelled externally
            )
            | "Redistribute" >> beam.Reshuffle()
            | "CreateTransaction" >> beam.Map(generate_transaction)
            | "WriteToBigQuery"
            >> beam.io.WriteToBigQuery(
                table=known_args.output_table,
                schema=TABLE_SCHEMA,
                method=beam.io.WriteToBigQuery.Method.STORAGE_WRITE_API,
                create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                # Trigger frequent commits (simulates Kafka behavior)
                triggering_frequency=1,
            )
        )


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    run()
