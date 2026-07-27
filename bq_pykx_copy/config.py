"""
Central configuration for the kdb+ -> Parquet -> BigQuery PoC.

IMPORTANT: import this module *before* `import pykx` anywhere, because PyKX reads
its licensing environment variables at import time.  Every script here does
`import config` on the first line for exactly that reason.
"""

from __future__ import annotations

import base64
import os
import pathlib
import subprocess

from dotenv import load_dotenv

HERE = pathlib.Path(__file__).resolve().parent

# Load .env (if present) so KDB_LICENSE_B64 / GCP_* are available.
load_dotenv(HERE / ".env")

# --------------------------------------------------------------------------- #
# PyKX licensing
# --------------------------------------------------------------------------- #
# Ways to supply the license, in priority order:
#   1. a binary kc.lic (or k4.lic) file in this folder  (preferred; q reads it
#      via $QLIC).
#   2. KDB_LICENSE_B64 in .env    (base64 of a personal kc.lic), or
#      KDB_K4LICENSE_B64 in .env  (base64 of a commercial k4.lic) - we decode it
#      to a file ourselves, which is more reliable than PyKX's non-interactive
#      handling.
# This must run before `import pykx` (done via `import config` first everywhere).
_LOCAL_KC = HERE / "kc.lic"
_LOCAL_K4 = HERE / "k4.lic"

if not _LOCAL_KC.exists() and not _LOCAL_K4.exists():
    _kc_b64 = os.getenv("KDB_LICENSE_B64", "").strip()
    _k4_b64 = os.getenv("KDB_K4LICENSE_B64", "").strip()
    if _kc_b64:
        _LOCAL_KC.write_bytes(base64.b64decode(_kc_b64))
    elif _k4_b64:
        _LOCAL_K4.write_bytes(base64.b64decode(_k4_b64))

if _LOCAL_KC.exists() or _LOCAL_K4.exists():
    # QLIC = directory containing kc.lic/k4.lic; this is what embedded q reads.
    os.environ["QLIC"] = str(HERE)


def resolve_gcp_project() -> str:
    """Return GCP_PROJECT from env, else the active gcloud/ADC default project."""
    proj = os.getenv("GCP_PROJECT", "").strip()
    if proj:
        return proj
    try:
        proj = subprocess.check_output(
            ["gcloud", "config", "get-value", "project"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        proj = ""
    if not proj or proj == "(unset)":
        raise RuntimeError(
            "No GCP project found. Set GCP_PROJECT in .env or run "
            "`gcloud config set project <id>`."
        )
    return proj


# --------------------------------------------------------------------------- #
# GCP targets
# --------------------------------------------------------------------------- #
GCS_BUCKET = os.getenv("GCS_BUCKET", "").strip()
GCS_PREFIX = os.getenv("GCS_PREFIX", "kdb_migration_poc").strip("/")
BQ_DATASET = os.getenv("BQ_DATASET", "kdb_migration_poc").strip()
BQ_TABLE = os.getenv("BQ_TABLE", "firm_orderbook_poc").strip()
BQ_LOCATION = os.getenv("BQ_LOCATION", "US").strip()

# --------------------------------------------------------------------------- #
# Local paths
# --------------------------------------------------------------------------- #
DATA_DIR = HERE / "data"
HDB_DIR = DATA_DIR / "hdb"  # synthetic kdb+ HDB lives here
PARQUET_DIR = DATA_DIR / "parquet"  # converted parquet files land here
DATA_DIR.mkdir(exist_ok=True)
HDB_DIR.mkdir(parents=True, exist_ok=True)
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Run knobs
# --------------------------------------------------------------------------- #
POC_ROWS = int(os.getenv("POC_ROWS", "1000000"))
POC_DATES = [
    d.strip()
    for d in os.getenv("POC_DATES", "2024.01.02,2024.01.03").split(",")
    if d.strip()
]
PARQUET_ROW_GROUP = int(os.getenv("PARQUET_ROW_GROUP", "250000"))

# --------------------------------------------------------------------------- #
# Timestamp handling policy  (see README "Timestamp handling")
# --------------------------------------------------------------------------- #
# Plain kdb+ timestamps -> BigQuery TIMESTAMP at MICROSECOND precision (human
# readable in BQ); the last 3 nanosecond digits are truncated.
#
# Event timestamps that must stay LOSSLESS (a customer DDL does exactly this,
# e.g. `timestampNanos INT64`) are flagged `is_event_ts_nanos=True` in schema.py
# and stored as INT64 "nanoseconds since 1970". See kdb_utils.arrow_align().
