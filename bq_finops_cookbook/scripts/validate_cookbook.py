#!/usr/bin/env python3
"""Static offline contract validator for the BigQuery FinOps cookbook."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List

from extract_sql import extract_named_queries

EXPECTED_QUERY_IDS = {
    "0.1", "0.2", "0.2a", "0.3", "0.4", "0.5",
    "1.1", "1.2", "1.3", "4.1", "4.2", "4.3", "4.4", "4.5",
    "4.8", "4.9", "4.10", "4.11", "4.12", "4.13", "4.14",
    "5.1", "6.1", "6.2", "6.3",
}
FINAL_HEADINGS = (
    "Current State Summary", "Evidence Quality", "Recommended Strategy",
    "Alternative Analysis", "Optimization Actions", "Implementation Proposals",
    "Validation Criteria", "Documentation Checks", "MCP / bq Execution Notes",
    "Next Steps",
)


def run_checks(root: Path) -> List[str]:
    failures: List[str] = []
    skill = root / ".agents/skills/bq-finops-analyst/SKILL.md"
    resource = skill.parent / "resources/finops_agent.md"
    canonical = [root / "README.md", skill, resource]

    frontmatter_name = re.search(r"^name:\s*([^\s]+)$", skill.read_text(), re.MULTILINE)
    if not frontmatter_name or frontmatter_name.group(1) != skill.parent.name:
        failures.append("skill frontmatter name must exactly match its parent directory")

    try:
        queries = extract_named_queries(resource.read_text())
        ids = {query["id"] for query in queries}
        if ids != EXPECTED_QUERY_IDS:
            failures.append(f"query inventory mismatch: missing={sorted(EXPECTED_QUERY_IDS - ids)} extra={sorted(ids - EXPECTED_QUERY_IDS)}")
    except (OSError, ValueError) as exc:
        failures.append(f"query extraction failed: {exc}")

    for name in ("claim_matrix.json", "execution_manifest.json"):
        path = resource.parent / name
        try:
            json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"invalid {name}: {exc}")

    price_pattern = re.compile(r"\$?6\.25\s*(?:/|per\s+)(?:TB|TiB)")
    for path in canonical:
        text = path.read_text()
        if "docs/REFERENCES.md" in text:
            failures.append(f"stale reference path: {path.relative_to(root)}")
        if price_pattern.search(text):
            failures.append(f"embedded volatile on-demand price: {path.relative_to(root)}")

    agent_text = resource.read_text()
    dangerous_patterns = {
        "unqualified regional INFORMATION_SCHEMA view": r"`region-\[YOUR_REGION\]`\.INFORMATION_SCHEMA",
        "Storage Write API success counted as error": r"error_code\s*!=\s*''",
        "stale fixed ingestion savings": r"50% cost savings|\$0\.025/GiB|\$0\.05/GiB",
        "unqualified exactly-once claim": r"exactly-once delivery semantics",
        "broken cumulative commitment reconstruction": r"slot_cumulative|slot_cummulative",
        "destructive reservation removal command": r"\bbq\s+rm\s+--reservation\b",
        "invalid Standard 2500-slot guidance": r"(?:2,500|2500)[^\n]{0,80}Standard|Standard[^\n]{0,80}(?:2,500|2500)",
    }
    for label, pattern in dangerous_patterns.items():
        if re.search(pattern, agent_text, re.IGNORECASE):
            failures.append(label)
    if "COUNT(DISTINCT IF(state = 'PENDING' AND priority = 'INTERACTIVE'" not in agent_text:
        failures.append("queue pressure must count distinct pending interactive jobs per second")
    required_runtime_contracts = {
        "performance insights must be filtered, not only projected": (
            agent_text.count("WHERE insights.input_data_change.records_read_diff_percentage IS NOT NULL") >= 2
            and agent_text.count("WHERE insights.slot_contention") >= 2
        ),
        "Storage Write API grouping must preserve project/dataset/table/stream identity":
            "GROUP BY start_timestamp, project_id, dataset_id, table_id, stream_type" in agent_text,
        "logical storage forecast must exclude deleted logical bytes":
            "SUM(IF(deleted = FALSE, active_logical_bytes, 0))" in agent_text
            and "SUM(IF(deleted = FALSE, long_term_logical_bytes, 0))" in agent_text,
        "storage forecast must restrict supported base tables":
            "table_type = 'BASE TABLE'" in agent_text
            and "total_physical_bytes + fail_safe_physical_bytes > 0" in agent_text,
        "partition triage must rank primarily by distinct referencing jobs":
            "ORDER BY\n  r.referencing_jobs DESC," in agent_text,
        "current configuration report must be unconditional":
            "Always generate `analysis_results/00_current_configuration.md`" in agent_text,
    }
    for label, satisfied in required_runtime_contracts.items():
        if not satisfied:
            failures.append(label)
    for block in re.findall(r"```(?:bash|shell)\n(.*?)```", agent_text, re.DOTALL):
        if "--scaling_mode=AUTOSCALE_ONLY" in block and "--ignore_idle_slots=true" not in block:
            failures.append("AUTOSCALE_ONLY proposal requires ignore_idle_slots=true")

    for path in (root / "sample_results").rglob("*.md"):
        text = path.read_text()
        if "**Synthetic sample:**" not in text[:500]:
            failures.append(f"sample is not marked synthetic: {path.relative_to(root)}")
        if re.search(r"\$\s*\d", text):
            failures.append(f"synthetic sample embeds unverified dollar amount: {path.relative_to(root)}")
        if re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE):
            failures.append(f"synthetic sample embeds email-like principal: {path.relative_to(root)}")
        misleading_sample_patterns = {
            "reservation simulation wording": r"^## Reservation Simulation\s*$",
            "per-job averages presented as capacity absorption": r"absorb 100%|would comfortably absorb",
            "general recommendations absence presented as Slot Recommender evidence":
                r"absence of recommendations is consistent|Slot Recommender has no basis or need",
            "default cross-project ranking from project-scoped evidence": r"## Project Rankings|\*\*Top 3 Projects:\*\*",
        }
        for label, pattern in misleading_sample_patterns.items():
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                failures.append(f"{label}: {path.relative_to(root)}")
        if path.name == "06_final_recommendation.md":
            headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
            missing = [heading for heading in FINAL_HEADINGS if heading not in headings]
            if missing:
                failures.append(f"final report missing headings {missing}: {path.relative_to(root)}")
            elif [headings.index(heading) for heading in FINAL_HEADINGS] != sorted(headings.index(heading) for heading in FINAL_HEADINGS):
                failures.append(f"final report headings out of order: {path.relative_to(root)}")

    for path in root.rglob("*.md"):
        if ".hermes" in path.parts:
            continue
        for block in re.findall(r"```(?:bash|shell)\n(.*?)```", path.read_text(), re.DOTALL):
            if "--edition=STANDARD" not in block and "--edition STANDARD" not in block:
                continue
            values = [int(value) for value in re.findall(r"--(?:autoscale_max_slots|max_slots)[= ](\d+)", block)]
            if values and max(values) > 1600:
                failures.append(f"Standard reservation exceeds 1600 slots: {path.relative_to(root)}")

    return failures


def inventory(root: Path) -> int:
    resource = root / ".agents/skills/bq-finops-analyst/resources/finops_agent.md"
    queries = extract_named_queries(resource.read_text())
    samples = list((root / "sample_results").rglob("*.md"))
    print(json.dumps({"queries": len(queries), "samples": len(samples), "query_ids": [query["id"] for query in queries]}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("all", "inventory"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "inventory":
        return inventory(root)
    failures = run_checks(root)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: cookbook static offline contracts are green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
