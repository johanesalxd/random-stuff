"""CLI for exporting BigQuery Property Graph DDL, FK constraints, and verified queries.

Exports semantic contracts into:
  - BigQuery Property Graph DDL (CREATE PROPERTY GRAPH + MEASURE())
  - Non-enforced PK/FK constraints DDL + pre-flight validation queries
  - Authored verified queries (YAML/JSON/SQL)
  - v1beta Data Agent datasource references JSON
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from semantic.graph_export import (  # noqa: E402
    build_data_agent_datasource_references,
    export_fk_constraints_ddl,
    export_property_graph_ddl,
    export_verified_queries,
)
from semantic.registry import load_contract  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser for export_semantic_layer.py."""
    parser = argparse.ArgumentParser(
        description="Export BigQuery Property Graph DDL, constraints, and verified queries from semantic contracts."
    )
    parser.add_argument(
        "--contract",
        required=True,
        help="Path to the semantic contract YAML file (e.g. config/semantic_contracts/thelook_orders.yaml).",
    )
    parser.add_argument(
        "--graph-project",
        default="my-gcp-project",
        help="Target GCP project for Property Graph DDL.",
    )
    parser.add_argument(
        "--graph-dataset",
        default="analytics_graph",
        help="Target BigQuery dataset for Property Graph DDL.",
    )
    parser.add_argument(
        "--graph-name",
        default=None,
        help="Optional Property Graph name (defaults to {contract_id}_graph).",
    )
    parser.add_argument(
        "--target-project",
        default="my-gcp-project",
        help="Target GCP project for PK/FK constraints DDL (cannot be bigquery-public-data).",
    )
    parser.add_argument(
        "--target-dataset",
        default="analytics_curated",
        help="Target BigQuery dataset for PK/FK constraints DDL.",
    )
    parser.add_argument(
        "--format",
        choices=["all", "graph-ddl", "fk-ddl", "verified-queries", "datasource-json"],
        default="all",
        help="Export format (default: all).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional file path or directory to write exported artifacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    contract_path = Path(args.contract)
    if not contract_path.is_file():
        sys.stderr.write(f"Error: contract file not found: {args.contract}\n")
        return 1

    contract = load_contract(contract_path)

    outputs: dict[str, str] = {}

    if args.format in ("all", "graph-ddl"):
        graph_res = export_property_graph_ddl(
            contract,
            graph_project=args.graph_project,
            graph_dataset=args.graph_dataset,
            graph_name=args.graph_name,
        )
        outputs["graph.sql"] = graph_res.ddl

    if args.format in ("all", "fk-ddl"):
        fk_ddl = export_fk_constraints_ddl(
            contract,
            target_project=args.target_project,
            target_dataset=args.target_dataset,
        )
        outputs["constraints.sql"] = fk_ddl

    if args.format in ("all", "verified-queries"):
        vqs = export_verified_queries(contract)
        vq_data = [
            {"query_id": vq.query_id, "question": vq.question, "sql": vq.sql}
            for vq in vqs
        ]
        outputs["verified_queries.json"] = json.dumps(vq_data, indent=2)

    if args.format in ("all", "datasource-json"):
        ds_refs = build_data_agent_datasource_references(
            contract,
            graph_project=args.graph_project,
            graph_dataset=args.graph_dataset,
            graph_name=args.graph_name,
        )
        outputs["datasource_references.json"] = json.dumps(ds_refs, indent=2)

    if args.out:
        out_path = Path(args.out)
        if len(outputs) == 1 and not out_path.is_dir() and not args.out.endswith("/"):
            # Write single output directly to file
            single_content = next(iter(outputs.values()))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(single_content, encoding="utf-8")
            print(f"Wrote {out_path}")
        else:
            out_path.mkdir(parents=True, exist_ok=True)
            for fname, content in outputs.items():
                target_file = out_path / fname
                target_file.write_text(content, encoding="utf-8")
                print(f"Wrote {target_file}")
    else:
        if len(outputs) == 1:
            print(next(iter(outputs.values())))
        else:
            for fname, content in outputs.items():
                print(f"-- === {fname} ===")
                print(content)
                print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
