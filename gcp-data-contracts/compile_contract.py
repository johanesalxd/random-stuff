#!/usr/bin/env python3
"""compile_contract.py — Open Data Contract Standard (ODCS) Compiler for GCP.

Compiles an ODCS v3.0 contract (contract.odcs.yaml) into:
  1. Pub/Sub Avro Schema (schemas/trade_event_v1.avsc)
  2. BigQuery Table DDL (sql/create_trades_table.sql)
  3. Dataplex Auto Data Quality YAML Spec (config/dataplex_dq_spec.yaml)

Zero heavy external dependencies (Pure Python 3 standard library + PyYAML).
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    sys.stderr.write("Error: PyYAML is required. Run 'pip install pyyaml'.\n")
    sys.exit(1)


# Custom PyYAML Dumper to format indented sequence blocks nicely
class IndentedYamlDumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


# -----------------------------------------------------------------------------
# Type System Mappings
# -----------------------------------------------------------------------------

ODCS_TO_AVRO_TYPE: Dict[str, Any] = {
    "string": "string",
    "number": "double",
    "integer": "long",
    "int": "int",
    "long": "long",
    "float": "float",
    "double": "double",
    "timestamp": "string",  # ISO-8601 formatted string for Pub/Sub JSON
    "boolean": "boolean",
    "bool": "boolean",
}

ODCS_TO_BQ_TYPE: Dict[str, str] = {
    "string": "STRING",
    "number": "NUMERIC",
    "integer": "INT64",
    "int": "INT64",
    "long": "INT64",
    "float": "FLOAT64",
    "double": "FLOAT64",
    "timestamp": "TIMESTAMP",
    "boolean": "BOOL",
    "bool": "BOOL",
}

MANDATORY_SGX_COLUMNS = [
    "trade_id",
    "instrument_code",
    "price",
    "volume",
    "buyer_id",
    "seller_id",
    "trade_timestamp",
    "trade_status",
]


# -----------------------------------------------------------------------------
# Compiler Exception Classes
# -----------------------------------------------------------------------------

class ContractCompilerError(Exception):
    """Base exception for contract compilation errors."""
    pass


class ContractValidationError(ContractCompilerError):
    """Raised when the contract schema or metadata is invalid."""
    pass


# -----------------------------------------------------------------------------
# Contract Parser & Validator
# -----------------------------------------------------------------------------

class ContractModel:
    def __init__(self, raw_data: Dict[str, Any]):
        self.raw = raw_data
        self.api_version: str = str(raw_data.get("apiVersion", ""))
        self.kind: str = str(raw_data.get("kind", ""))
        self.id: str = str(raw_data.get("id", ""))
        self.name: str = str(raw_data.get("name", "contract"))
        self.version: str = str(raw_data.get("version", "1.0.0"))
        self.description_doc: str = self._extract_description(raw_data.get("description"))

        # Servers configuration
        self.servers: Dict[str, Any] = raw_data.get("servers", {})

        # Extract primary dataset properties
        self.table_name, self.properties, self.metadata_properties = self._extract_schema(raw_data)

        # SLAs and Quality rules
        self.sla: Dict[str, Any] = raw_data.get("sla", raw_data.get("servicelevels", {}))
        self.quality_rules: List[Dict[str, Any]] = raw_data.get("quality", [])

        # Validate mandatory structure
        self._validate()

    def _extract_description(self, desc: Any) -> str:
        if isinstance(desc, dict):
            return desc.get("purpose", desc.get("summary", "Data Contract"))
        return str(desc or "Data Contract")

    def _extract_schema(self, raw: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        # Support ODCS v3 'schema' list of datasets
        if "schema" in raw and isinstance(raw["schema"], list) and len(raw["schema"]) > 0:
            dataset = raw["schema"][0]
            table_name = dataset.get("name", dataset.get("physicalName", "equity_trades"))
            props = dataset.get("properties", [])
            meta_props = dataset.get("metadataProperties", [])
            return table_name, props, meta_props

        # Support backward-compatibility with v2 'models'
        if "models" in raw and isinstance(raw["models"], dict):
            first_model_key = next(iter(raw["models"]))
            model = raw["models"][first_model_key]
            fields = model.get("fields", {})
            props = []
            if isinstance(fields, dict):
                for fname, fmeta in fields.items():
                    prop = dict(fmeta)
                    prop["name"] = fname
                    props.append(prop)
            elif isinstance(fields, list):
                props = fields
            meta_props = model.get("metadataProperties", [])
            return first_model_key, props, meta_props

        raise ContractValidationError("Contract does not contain a valid 'schema' or 'models' section.")

    def _validate(self) -> None:
        if not self.api_version:
            raise ContractValidationError("Contract missing 'apiVersion'.")
        if not self.properties:
            raise ContractValidationError(f"No properties found for table '{self.table_name}'.")

        # Verify presence of mandatory SGX columns
        prop_names = {p.get("name") for p in self.properties}
        missing = [col for col in MANDATORY_SGX_COLUMNS if col not in prop_names]
        if missing:
            raise ContractValidationError(
                f"Contract is missing mandatory SGX Equity Trade column(s): {', '.join(missing)}"
            )


def load_contract(contract_path: Path) -> ContractModel:
    if not contract_path.exists():
        raise ContractCompilerError(f"Contract file not found: {contract_path}")

    try:
        content = contract_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ContractCompilerError(f"Error reading {contract_path}: {e}")

    if not content.strip():
        raise ContractValidationError(f"Contract file {contract_path} is empty.")

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ContractValidationError(f"Failed to parse YAML in {contract_path}: {e}")

    if not isinstance(data, dict):
        raise ContractValidationError(f"Contract file {contract_path} must contain a YAML mapping/dictionary.")

    return ContractModel(data)


# -----------------------------------------------------------------------------
# Compilers
# -----------------------------------------------------------------------------

def compile_avro_schema(model: ContractModel) -> str:
    """Compiles the contract model into a Pub/Sub compatible Avro JSON schema."""
    fields = []
    for prop in model.properties:
        name = prop.get("name")
        logical_type = str(prop.get("logicalType", "string")).lower()
        doc = prop.get("description", "")
        enum_values = prop.get("enum")

        if enum_values and isinstance(enum_values, list):
            # Generate Avro Enum definition
            enum_type_name = "".join(part.capitalize() for part in name.split("_"))
            field_type = {
                "type": "enum",
                "name": enum_type_name,
                "symbols": [str(v) for v in enum_values],
            }
        else:
            field_type = ODCS_TO_AVRO_TYPE.get(logical_type, "string")

        field_obj: Dict[str, Any] = {
            "name": name,
            "type": field_type,
        }
        if doc:
            field_obj["doc"] = doc

        fields.append(field_obj)

    avro_schema = {
        "type": "record",
        "name": "TradeEvent",
        "namespace": "com.sgx.equity",
        "doc": "SGX Real-Time Equity Trade Event Schema v1",
        "fields": fields,
    }

    return json.dumps(avro_schema, indent=2, ensure_ascii=False) + "\n"


def compile_bigquery_ddl(
    model: ContractModel, project_id: str, dataset_id: str, table_id: str, replace: bool = False
) -> str:
    """Compiles the contract model into a partitioned BigQuery DDL."""
    table_action = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE IF NOT EXISTS"
    lines = [
        "-- SGX Equity Trades Table DDL",
        "-- Generated deterministically by compile_contract.py from contract.odcs.yaml",
        "-- Governed by Open Data Contract Standard (ODCS) v3.0.0",
        "",
        f"{table_action} `{project_id}.{dataset_id}.{table_id}`",
        "(",
    ]

    col_defs = []
    primary_keys = []

    for prop in model.properties:
        col_name = prop.get("name")
        logical_type = str(prop.get("logicalType", "string")).lower()
        physical_type = prop.get("physicalType")
        required = prop.get("required", True)
        is_pk = prop.get("primaryKey", False)
        desc = prop.get("description", "")

        bq_type = physical_type or ODCS_TO_BQ_TYPE.get(logical_type, "STRING")
        nullability = " NOT NULL" if required else ""
        escaped_desc = desc.replace('"', '\\"')
        options = f' OPTIONS(description="{escaped_desc}")' if desc else ""

        col_defs.append(f"  {col_name} {bq_type}{nullability}{options}")

        if is_pk:
            primary_keys.append(col_name)

    # Append Pub/Sub Metadata Ingestion Columns required for --write-metadata
    col_defs.append("  -- Pub/Sub Metadata Ingestion Columns (required for --write-metadata)")

    # Use metadata properties from contract if defined, else defaults
    meta_props = model.metadata_properties or [
        {"name": "subscription_name", "physicalType": "STRING", "description": "Pub/Sub subscription that delivered the message"},
        {"name": "message_id", "physicalType": "STRING", "description": "Pub/Sub message identifier"},
        {"name": "publish_time", "physicalType": "TIMESTAMP", "description": "Pub/Sub message publish timestamp"},
        {"name": "attributes", "physicalType": "STRING", "description": "Pub/Sub message attributes formatted as JSON"},
    ]

    for mprop in meta_props:
        mname = mprop.get("name")
        mtype = mprop.get("physicalType", "STRING")
        mdesc = mprop.get("description", "").replace('"', '\\"')
        mopt = f' OPTIONS(description="{mdesc}")' if mdesc else ""
        col_defs.append(f"  {mname} {mtype}{mopt}")

    if primary_keys:
        pk_str = ", ".join(primary_keys)
        col_defs.append(f"  PRIMARY KEY ({pk_str}) NOT ENFORCED")

    lines.append(",\n".join(col_defs))
    lines.append(")")
    lines.append("PARTITION BY DATE(trade_timestamp)")
    lines.append("CLUSTER BY instrument_code, trade_status")
    lines.append("OPTIONS(")
    lines.append(
        '  description="Real-time and historical equity trade executions on the Singapore Exchange (governed by ODCS contract)"'
    )
    lines.append(");")
    lines.append("")

    return "\n".join(lines)


def compile_dataplex_spec(
    model: ContractModel, project_id: str, dataset_id: str, table_id: str
) -> str:
    """Compiles the contract SLAs and quality rules into a Dataplex Auto DQ YAML specification."""
    rules: List[Dict[str, Any]] = []

    # Quality rules from contract
    for q in model.quality_rules:
        qtype = str(q.get("type", "")).lower()
        dim = q.get("dimension", "VALIDITY")
        col = q.get("column")
        desc = q.get("description", "")
        threshold = float(q.get("threshold", 1.0))

        rule_entry: Dict[str, Any] = {
            "description": desc or f"Rule for {col or 'table'}",
            "dimension": dim,
        }
        if col:
            rule_entry["column"] = col
        rule_entry["threshold"] = threshold

        if qtype == "completeness":
            rule_entry["nonNullExpectation"] = {}
            rules.append(rule_entry)

        elif qtype == "range":
            rule_entry["ignoreNull"] = False
            range_dict: Dict[str, Any] = {}
            if "minValue" in q:
                range_dict["minValue"] = str(q["minValue"])
            if "maxValue" in q:
                range_dict["maxValue"] = str(q["maxValue"])
            if "strictMinEnabled" in q:
                range_dict["strictMinEnabled"] = bool(q["strictMinEnabled"])
            if "strictMaxEnabled" in q:
                range_dict["strictMaxEnabled"] = bool(q["strictMaxEnabled"])
            rule_entry["rangeExpectation"] = range_dict
            rules.append(rule_entry)

        elif qtype == "set":
            rule_entry["setExpectation"] = {
                "values": [str(v) for v in q.get("values", [])]
            }
            rules.append(rule_entry)

        elif qtype == "freshness":
            sql_expr = q.get("sqlExpression")
            if not sql_expr:
                max_age = q.get("maxAge", "2h").upper()
                val = max_age[:-1] if max_age.endswith("H") or max_age.endswith("D") else "2"
                unit = "DAY" if max_age.endswith("D") else "HOUR"
                sql_expr = f"{col} >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {val} {unit})"
            rule_entry["rowConditionExpectation"] = {
                "sqlExpression": sql_expr
            }
            rules.append(rule_entry)

        elif qtype in ("sql_assertion", "sql"):
            # Prefer rowConditionExpectation if rowCondition or sqlExpression is provided
            if "rowCondition" in q or "sqlExpression" in q:
                rule_entry["rowConditionExpectation"] = {
                    "sqlExpression": q.get("rowCondition") or q.get("sqlExpression")
                }
            elif "sqlStatement" in q:
                rule_entry.pop("threshold", None)
                rule_entry["sqlAssertion"] = {
                    "sqlStatement": q["sqlStatement"]
                }
            rules.append(rule_entry)

        elif qtype == "row_condition":
            rule_entry["rowConditionExpectation"] = {
                "sqlExpression": q.get("sqlExpression", "")
            }
            rules.append(rule_entry)

    spec_data: Dict[str, Any] = {
        "samplingPercent": 100,
        "rules": rules,
        "postScanActions": {
            "bigqueryExport": {
                "resultsTable": f"projects/{project_id}/datasets/{dataset_id}/tables/dq_export_results"
            }
        },
        "catalogPublishingEnabled": True,
    }

    yaml_str = yaml.dump(
        spec_data,
        Dumper=IndentedYamlDumper,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
    )
    return yaml_str


# -----------------------------------------------------------------------------
# File Writing & Idempotency / Drift Verification
# -----------------------------------------------------------------------------

def write_if_changed(target_path: Path, content: str) -> str:
    """Writes content to target_path only if it differs from current content.

    Returns status: 'CREATED', 'UPDATED', or 'UNCHANGED'.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        try:
            existing = target_path.read_text(encoding="utf-8")
            if existing == content:
                return "UNCHANGED"
        except Exception:
            pass  # Fall through to write
        target_path.write_text(content, encoding="utf-8")
        return "UPDATED"
    else:
        target_path.write_text(content, encoding="utf-8")
        return "CREATED"


def check_file_drift(target_path: Path, generated_content: str) -> Tuple[bool, str]:
    """Compares generated_content against target_path.

    Returns (matches: bool, diff_or_reason: str).
    """
    if not target_path.exists():
        return False, f"File does not exist: {target_path}"

    try:
        disk_content = target_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Failed to read {target_path}: {e}"

    if disk_content == generated_content:
        return True, ""

    diff = difflib.unified_diff(
        disk_content.splitlines(keepends=True),
        generated_content.splitlines(keepends=True),
        fromfile=f"disk:{target_path}",
        tofile="generated:in-memory",
    )
    return False, "".join(diff)


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile Open Data Contract Standard (ODCS) YAML into Avro, BigQuery DDL, and Dataplex YAML.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("contract.odcs.yaml"),
        help="Path to the input ODCS YAML contract file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Root output directory for generated artifacts.",
    )
    parser.add_argument(
        "--avro-out",
        type=Path,
        default=None,
        help="Path for generated Avro schema file (overrides default).",
    )
    parser.add_argument(
        "--sql-out",
        type=Path,
        default=None,
        help="Path for generated BigQuery DDL file (overrides default).",
    )
    parser.add_argument(
        "--dataplex-out",
        type=Path,
        default=None,
        help="Path for generated Dataplex DQ spec file (overrides default).",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=os.environ.get("PROJECT_ID", "${PROJECT_ID}"),
        help="GCP Project ID to substitute into DDL and Dataplex config.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="sgx_market_data",
        help="BigQuery Dataset ID.",
    )
    parser.add_argument(
        "--table",
        type=str,
        default="equity_trades",
        help="BigQuery Table ID.",
    )
    parser.add_argument(
        "--replace",
        "--recreate-tables",
        dest="replace",
        action="store_true",
        default=False,
        help="Emit 'CREATE OR REPLACE TABLE' instead of non-destructive 'CREATE TABLE IF NOT EXISTS'.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry-run verification mode. Checks if disk files match contract without writing.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # 1. Parse and validate contract
    try:
        model = load_contract(args.contract)
    except ContractCompilerError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    # 2. Compile artifacts in memory
    try:
        avro_content = compile_avro_schema(model)
        sql_content = compile_bigquery_ddl(model, args.project_id, args.dataset, args.table, replace=args.replace)
        dq_content = compile_dataplex_spec(model, args.project_id, args.dataset, args.table)
    except Exception as e:
        sys.stderr.write(f"Error during compilation: {e}\n")
        return 1

    # Determine artifacts to write or check
    output_dir: Path = args.output_dir
    custom_specified = any([args.avro_out, args.sql_out, args.dataplex_out])
    artifacts = []
    if custom_specified:
        if args.avro_out:
            artifacts.append(("Avro Schema", args.avro_out, avro_content))
        if args.sql_out:
            artifacts.append(("BigQuery DDL", args.sql_out, sql_content))
        if args.dataplex_out:
            artifacts.append(("Dataplex DQ Spec", args.dataplex_out, dq_content))
    else:
        artifacts = [
            ("Avro Schema", output_dir / "schemas" / "trade_event_v1.avsc", avro_content),
            ("BigQuery DDL", output_dir / "sql" / "create_trades_table.sql", sql_content),
            ("Dataplex DQ Spec", output_dir / "config" / "dataplex_dq_spec.yaml", dq_content),
        ]

    # 3. Handle --check mode
    if args.check:
        has_drift = False
        print(f"Checking artifacts against contract: {args.contract}")
        for label, path, content in artifacts:
            matches, diff_or_reason = check_file_drift(path, content)
            if matches:
                print(f"  [OK] {label}: {path} is up-to-date.")
            else:
                has_drift = True
                print(f"  [DRIFT] {label}: {path} out of sync or missing.")
                if diff_or_reason:
                    print(diff_or_reason)

        if has_drift:
            sys.stderr.write(
                "\nCheck failed: 1 or more artifacts are missing or out of sync with contract.\n"
                "Run 'python3 compile_contract.py' to regenerate artifacts.\n"
            )
            return 1

        print("\nAll generated artifacts are up-to-date.")
        return 0

    # 4. Handle write mode (idempotent write-if-changed)
    print(f"Compiling contract: {args.contract}")
    for label, path, content in artifacts:
        status = write_if_changed(path, content)
        print(f"  [{status}] {label} -> {path}")

    print("Compilation successful.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
