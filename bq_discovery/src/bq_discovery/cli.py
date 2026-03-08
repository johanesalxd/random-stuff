"""CLI entry point for bq-discovery."""

from __future__ import annotations

import argparse
import logging
import sys

from bq_discovery.models import ResourceType
from bq_discovery.scanner import run_scan

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="bq-discovery",
        description=(
            "Scan BigQuery permission access across projects in a GCP organization."
        ),
    )
    parser.add_argument(
        "--org-id",
        required=True,
        help="GCP organization ID (numeric).",
    )
    parser.add_argument(
        "--skip-acls",
        action="store_true",
        help=(
            "Skip the dataset ACL scan. Only IAM policies from Cloud Asset "
            "Inventory will be returned. Faster but misses legacy ACLs, "
            "specialGroup, domain, and authorized view/dataset/routine entries."
        ),
    )
    parser.add_argument(
        "--resource-types",
        default="dataset,table,view",
        help=(
            "Comma-separated list of resource types to scan. "
            "Options: dataset, table, view. Default: all."
        ),
    )
    parser.add_argument(
        "--project-ids",
        default=None,
        help=(
            "Comma-separated list of specific project IDs to scan. "
            "If not specified, discovers all projects in the org."
        ),
    )
    parser.add_argument(
        "--expand-groups",
        action="store_true",
        help=(
            "Expand group memberships to individual users. "
            "Requires Cloud Identity API and appropriate permissions."
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path for JSON results. If not specified, prints to stdout.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity. Use -v for INFO, -vv for DEBUG.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for bq-discovery CLI."""
    args = parse_args(argv)

    # Configure logging
    log_level = logging.WARNING
    if args.verbose >= 2:
        log_level = logging.DEBUG
    elif args.verbose >= 1:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Parse resource types
    resource_types: set[ResourceType] = set()
    for rt in args.resource_types.split(","):
        rt = rt.strip().lower()
        try:
            resource_types.add(ResourceType(rt))
        except ValueError:
            logger.error("Unknown resource type: %s", rt)
            print(
                f"Error: Unknown resource type '{rt}'. "
                f"Valid types: dataset, table, view",
                file=sys.stderr,
            )
            return 1

    # Parse project IDs
    project_ids = None
    if args.project_ids:
        project_ids = [p.strip() for p in args.project_ids.split(",")]

    # Run scan
    try:
        result = run_scan(
            organization_id=args.org_id,
            resource_types=resource_types,
            project_ids=project_ids,
            skip_acls=args.skip_acls,
            expand_groups=args.expand_groups,
        )
    except Exception as e:
        logger.error("Scan failed: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Output results
    json_output = result.to_json()
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_output)
            f.write("\n")
        logger.info("Results written to %s", args.output)
    else:
        print(json_output)

    # Summary to stderr
    print(
        f"\nScan complete: "
        f"{len(result.entries)} permission entries, "
        f"{result.projects_scanned} projects, "
        f"{result.datasets_scanned} datasets, "
        f"{result.resources_scanned} resources, "
        f"{len(result.errors)} errors",
        file=sys.stderr,
    )

    if result.errors:
        print(
            f"\nErrors ({len(result.errors)}):",
            file=sys.stderr,
        )
        for error in result.errors[:10]:
            print(f"  - {error}", file=sys.stderr)
        if len(result.errors) > 10:
            print(
                f"  ... and {len(result.errors) - 10} more",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
