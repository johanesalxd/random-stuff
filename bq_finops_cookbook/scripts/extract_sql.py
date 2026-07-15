#!/usr/bin/env python3
"""Extract named BigQuery SQL blocks from the cookbook resource file."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

QUERY_PATTERN = re.compile(
    r"^### Query (?P<id>[0-9]+(?:\.[0-9]+[a-z]?)?): (?P<title>[^\n]+)\n"
    r"(?:(?!^### Query ).)*?```sql\n(?P<sql>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)


def extract_named_queries(text: str) -> List[Dict[str, str]]:
    queries = [
        {
            "id": match.group("id"),
            "title": match.group("title").strip(),
            "sql": match.group("sql").strip(),
        }
        for match in QUERY_PATTERN.finditer(text)
    ]
    ids = [query["id"] for query in queries]
    if len(ids) != len(set(ids)):
        duplicates = sorted({query_id for query_id in ids if ids.count(query_id) > 1})
        raise ValueError(f"Duplicate query IDs: {', '.join(duplicates)}")
    return queries


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: extract_sql.py PATH", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    print(json.dumps(extract_named_queries(path.read_text()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
