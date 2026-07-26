"""
Anonymised schema for the PoC.

This is a *generic* wide order-book-style table that reproduces the real-world
migration challenge without any customer-specific names or data:

  * date-PARTITIONED (one kdb+ partition per day)
  * very WIDE  (428 columns in this synthetic build)
  * very SPARSE (most columns are null on any given row, because a row only
    populates the fields belonging to its own `message_type`)
  * a mix of INT64 / STRING / DATE columns
  * many NANOSECOND event-timestamps stored as INT64 (lossless)
  * one ingestion TIMESTAMP column (micro-second, human readable in BigQuery)

Each Column knows:
  - kdb_type : the kdb+/q type character used when generating synthetic data
  - bq_type  : the intended BigQuery type
  - null_ratio: fraction of rows that should be null (drives realistic sparsity)
  - is_event_ts_nanos: True for nanosecond timestamps we keep as INT64
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    kdb_type: str  # q type char: j=long, s=symbol, d=date, p=timestamp
    bq_type: str  # BigQuery type: INT64 / STRING / DATE / TIMESTAMP
    null_ratio: float  # 0.0 = never null, 1.0 = always null
    is_event_ts_nanos: bool = False


# --------------------------------------------------------------------------- #
# Synthetic "message types" -> each contributes a block of mostly-null columns.
# 12 groups x 35 fields = 420 message columns + 8 identity/metadata = 428 total.
# --------------------------------------------------------------------------- #
_N_MESSAGE_GROUPS = 12
_INT_FIELDS = [
    "country",
    "market",
    "instrument_group",
    "modifier",
    "commodity",
    "expiration_date",
    "strike_price",
    "order_number",
    "mp_quantity",
    "premium",
    "block",
    "time_validity",
    "exch_order_type",
    "open_close_req",
    "bid_or_ask",
    "order_type",
    "stop_condition",
    "total_volume",
    "delta_quantity",
    "balance_quantity",
    "display_quantity",
    "trade_price",
    "trade_quantity",
    "item_number",
    "deal_source",
]
_STR_FIELDS = [
    "country_id",
    "ex_customer",
    "user_id",
    "ex_client",
    "customer_info",
    "exchange_info",
    "otri_reserved",
    "give_up_country",
    "give_up_customer",
]


def _message_columns() -> list[Column]:
    cols: list[Column] = []
    for g in range(1, _N_MESSAGE_GROUPS + 1):
        # Group activation probability: only ~1/N rows are this message type,
        # so each group's columns are null the vast majority of the time.
        base_null = 1.0 - (1.0 / _N_MESSAGE_GROUPS) * (0.4 + 0.6 * (g % 3 == 0))
        base_null = min(0.9999, max(0.70, base_null))
        prefix = f"mt{g:02d}"
        for f in _INT_FIELDS:
            cols.append(Column(f"{prefix}__{f}", "j", "INT64", base_null))
        for f in _STR_FIELDS:
            cols.append(Column(f"{prefix}__{f}", "s", "STRING", base_null))
        # One nanosecond execution timestamp per group (kept as INT64, lossless).
        cols.append(
            Column(
                f"{prefix}__exec_timestamp_nanos",
                "p",
                "INT64",
                min(0.9999, base_null + 0.05),
                is_event_ts_nanos=True,
            )
        )
    return cols


def build_schema() -> list[Column]:
    """Full ordered column list for the synthetic table."""
    cols: list[Column] = [
        # Partition + identity (never null)
        Column("date", "d", "DATE", 0.0),
        Column("sym", "s", "STRING", 0.0),
        Column("message_type", "s", "STRING", 0.0),
    ]
    cols += _message_columns()
    # Footer / metadata columns (mostly never null) -----------------------------
    cols += [
        Column("seq_no", "j", "INT64", 0.0),
        # Primary event timestamp - nanosecond precision preserved as INT64.
        Column("timestamp_nanos", "p", "INT64", 0.0, is_event_ts_nanos=True),
        Column("receipt_timestamp_nanos", "p", "INT64", 0.0, is_event_ts_nanos=True),
        Column("file_name", "s", "STRING", 0.0),
        # Ingestion time - demonstrates the default micro-second TIMESTAMP path.
        Column("inserted_ts", "p", "TIMESTAMP", 0.0),
    ]
    return cols


def partition_column() -> str:
    """Return the column BigQuery should partition on (the kdb+ partition key)."""
    return "date"


def bq_clustering_columns() -> list[str]:
    """Return the default BigQuery clustering columns for order-book lookups."""
    return ["sym", "message_type"]


if __name__ == "__main__":
    s = build_schema()
    from collections import Counter

    print(f"Total columns: {len(s)}")
    print("By BigQuery type:", dict(Counter(c.bq_type for c in s)))
    print("Event ns-timestamp (INT64) columns:", sum(c.is_event_ts_nanos for c in s))
