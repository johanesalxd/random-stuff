#!/usr/bin/env python3
"""Analyze BigQuery table lineage with project-aware depth limiting.

This module traces upstream dependencies from a target table using the Data
Lineage API, with intelligent depth limiting based on project boundaries.
Continues unlimited traversal within the home project, then +N levels after
encountering any foreign project (default: +3).

Configuration:
    Optionally reads from config/migration_config.yaml for:
    - gcp.billing_project: Project for API billing
    - outputs.lineage: Output directory for lineage files

Prerequisites:
    pip install google-cloud-datacatalog-lineage
    gcloud services enable datalineage.googleapis.com --project=YOUR_PROJECT
    gcloud projects add-iam-policy-binding YOUR_PROJECT \
        --member="user:your-email@example.com" \
        --role="roles/datalineage.viewer"
"""

import argparse
from collections import defaultdict
from collections import deque
from datetime import datetime
import json
import os
import pickle
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add config directory to path for optional config loading
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
try:
    from config.config_loader import load_config, get_config_value
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

try:
    from google.api_core import exceptions as google_exceptions
    from google.cloud import datacatalog_lineage_v1
except ImportError:
    print("Error: Required package 'google-cloud-datacatalog-lineage' not found.")
    print("Install it with: pip install google-cloud-datacatalog-lineage")
    sys.exit(1)


def parse_table_name(table_name: str) -> Tuple[str, str, str]:
    """Parse fully qualified table name into components.

    Args:
        table_name: Fully qualified table name (project.dataset.table).

    Returns:
        Tuple of (project_id, dataset_id, table_id).

    Raises:
        ValueError: If table name format is invalid.
    """
    parts = table_name.split('.')
    if len(parts) != 3:
        raise ValueError(
            f"Invalid table name format: '{table_name}'. "
            "Expected format: project.dataset.table"
        )
    return parts[0], parts[1], parts[2]


def build_table_fqn(project: str, dataset: str, table: str) -> str:
    """Build fully qualified BigQuery resource name for Data Lineage API.

    Args:
        project: GCP project ID.
        dataset: BigQuery dataset ID.
        table: BigQuery table ID.

    Returns:
        Fully qualified resource name in format: bigquery:PROJECT.DATASET.TABLE
    """
    return f"bigquery:{project}.{dataset}.{table}"


def parse_table_fqn(fqn: str) -> Tuple[str, str, str]:
    """Parse BigQuery resource FQN into components.

    Args:
        fqn: Fully qualified resource name (bigquery:PROJECT.DATASET.TABLE).

    Returns:
        Tuple of (project, dataset, table).

    Raises:
        ValueError: If FQN format is invalid.
    """
    if not fqn.startswith("bigquery:"):
        raise ValueError(f"Invalid BigQuery FQN: {fqn}")

    table_path = fqn.replace("bigquery:", "")

    # Handle sharded table notation
    if table_path.startswith("sharded:"):
        table_path = table_path.replace("sharded:", "")

    parts = table_path.split(".")

    if len(parts) != 3:
        raise ValueError(f"Invalid BigQuery FQN format: {fqn}")

    return parts[0], parts[1], parts[2]


def get_lineage_client(location: str = "us") -> datacatalog_lineage_v1.LineageClient:
    """Initialize Data Lineage API client.

    Args:
        location: BigQuery location/region.

    Returns:
        Initialized LineageClient.

    Raises:
        Exception: If client initialization fails.
    """
    try:
        client = datacatalog_lineage_v1.LineageClient()
        return client
    except Exception as e:
        raise Exception(f"Failed to initialize Lineage API client: {e}")


def get_upstream_links(
    client: datacatalog_lineage_v1.LineageClient,
    table_fqn: str,
    project_id: str,
    location: str
) -> List[str]:
    """Get direct upstream dependencies for a table.

    Searches for lineage links where the table is the TARGET to find upstream sources.

    Args:
        client: Lineage API client.
        table_fqn: Fully qualified resource name of the table.
        project_id: GCP project ID for the API request.
        location: BigQuery location/region.

    Returns:
        List of upstream table FQNs (sources that feed into this table).
    """
    upstream_fqns = []

    try:
        request = datacatalog_lineage_v1.SearchLinksRequest(
            parent=f"projects/{project_id}/locations/{location}",
            target=datacatalog_lineage_v1.EntityReference(
                fully_qualified_name=table_fqn
            )
        )

        # Handle pagination
        while True:
            response = client.search_links(request=request)

            for link in response.links:
                if link.source and link.source.fully_qualified_name:
                    source_fqn = link.source.fully_qualified_name
                    if source_fqn.startswith("bigquery:"):
                        upstream_fqns.append(source_fqn)

            if not response.next_page_token:
                break

            request.page_token = response.next_page_token

    except google_exceptions.NotFound:
        pass
    except google_exceptions.PermissionDenied as e:
        print(
            f"Warning: Permission denied accessing lineage for {table_fqn}: {e}")
    except Exception as e:
        print(
            f"Warning: Error searching lineage for {table_fqn}: {type(e).__name__}: {e}")

    return upstream_fqns


def save_checkpoint(
    checkpoint_file: str,
    visited: set,
    levels: Dict[int, List[dict]],
    relationships: Dict[str, Dict],
    start_table: str,
    home_project: str,
    location: str,
    current_depth: int,
    foreign_depth_limit: int
) -> None:
    """Save checkpoint data to file using atomic writes.

    Args:
        checkpoint_file: Path to checkpoint file.
        visited: Set of visited table FQNs.
        levels: Dictionary of levels with table information.
        relationships: Dictionary of table relationships.
        start_table: Target table name.
        home_project: Home project ID.
        location: BigQuery location.
        current_depth: Current maximum depth reached.
        foreign_depth_limit: Depth limit for foreign projects.

    Raises:
        Exception: If checkpoint save fails.
    """
    checkpoint_data = {
        'visited': visited,
        'levels': levels,
        'relationships': relationships,
        'start_table': start_table,
        'home_project': home_project,
        'location': location,
        'current_depth': current_depth,
        'foreign_depth_limit': foreign_depth_limit,
        'timestamp': datetime.now().isoformat()
    }

    temp_file = f"{checkpoint_file}.tmp"

    try:
        with open(temp_file, 'wb') as f:
            pickle.dump(checkpoint_data, f)

        with open(temp_file, 'rb') as f:
            pickle.load(f)

        os.replace(temp_file, checkpoint_file)

        print(f"Checkpoint saved to: {checkpoint_file}")

    except Exception as e:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        raise Exception(f"Failed to save checkpoint: {e}")


def load_checkpoint(checkpoint_file: str) -> Optional[Dict]:
    """Load checkpoint data from file.

    Args:
        checkpoint_file: Path to checkpoint file.

    Returns:
        Checkpoint data dictionary or None if file doesn't exist.
    """
    try:
        with open(checkpoint_file, 'rb') as f:
            checkpoint_data = pickle.load(f)
        print(f"Checkpoint loaded from: {checkpoint_file}")
        print(f"  Previous depth: {checkpoint_data['current_depth']}")
        print(
            f"  Tables discovered: {sum(len(tables) for tables in checkpoint_data['levels'].values())}")
        print(f"  Timestamp: {checkpoint_data['timestamp']}")
        return checkpoint_data
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Warning: Failed to load checkpoint: {e}")
        return None


def trace_lineage_with_project_limit(
    client: datacatalog_lineage_v1.LineageClient,
    start_table: str,
    location: str = "us",
    foreign_depth_limit: int = 3,
    max_depth: int = 0,
    checkpoint_file: Optional[str] = None,
    resume_checkpoint: Optional[str] = None
) -> Dict[int, List[dict]]:
    """Recursively trace lineage with project-aware depth limiting.

    Continues unlimited traversal within the home project. Once any foreign
    project is encountered, continues for only +N more levels and stops.

    If max_depth is specified (> 0), it overrides project-aware logic and
    applies simple depth limiting.

    Args:
        client: Lineage API client.
        start_table: Fully qualified table name (project.dataset.table).
        location: BigQuery location/region.
        foreign_depth_limit: Levels to traverse after leaving home project.
        max_depth: Maximum depth to traverse (0 for project-aware limiting).
        checkpoint_file: Path to save checkpoint file (optional).
        resume_checkpoint: Path to resume from checkpoint file (optional).

    Returns:
        Dictionary with levels as keys and list of table info dicts as values.
    """
    checkpoint_data = None
    if resume_checkpoint:
        checkpoint_data = load_checkpoint(resume_checkpoint)
        if checkpoint_data:
            if checkpoint_data['start_table'] != start_table:
                print(
                    f"Warning: Checkpoint is for different table ({checkpoint_data['start_table']})")
                print("Starting fresh traversal...")
                checkpoint_data = None
            elif checkpoint_data['location'] != location:
                print(
                    f"Warning: Checkpoint is for different location ({checkpoint_data['location']})")
                print("Starting fresh traversal...")
                checkpoint_data = None

    try:
        project, dataset, table = parse_table_name(start_table)
    except ValueError as e:
        print(f"Error: {e}")
        return {}

    home_project = project
    start_fqn = build_table_fqn(project, dataset, table)

    if checkpoint_data:
        print(f"\n{'='*80}")
        print(f"RESUMING PROJECT-AWARE LINEAGE TRACE")
        print(f"{'='*80}")
        print(f"Target: {start_table}")
        print(f"Home Project: {home_project}")
        if max_depth > 0:
            print(f"Max Depth: {max_depth} (overrides project-aware limiting)")
        else:
            print(f"Foreign Project Depth Limit: +{foreign_depth_limit}")
        print(f"Location: {location}")
        print(f"Previous depth: {checkpoint_data['current_depth']}")
        print(f"{'='*80}\n")

        visited = checkpoint_data['visited']
        levels = defaultdict(list, checkpoint_data['levels'])
        relationships = defaultdict(
            lambda: {'parents': set(), 'children': set(), 'level': None, 'levels_since_foreign': 0},
            checkpoint_data['relationships']
        )

        queue = deque()
        prev_depth = checkpoint_data['current_depth']

        if prev_depth in levels:
            for table_info in levels[prev_depth]:
                table_fqn = table_info['fqn']
                if table_fqn in relationships:
                    for child_fqn in relationships[table_fqn].get('children', set()):
                        if child_fqn not in visited:
                            try:
                                child_project, _, _ = parse_table_fqn(child_fqn)
                                parent_foreign_count = relationships[table_fqn].get('levels_since_foreign', 0)
                                queue.append(
                                    (child_fqn, prev_depth + 1, child_project, parent_foreign_count))
                            except ValueError:
                                continue

        print(
            f"Resuming from Level {prev_depth}: queuing {len(queue)} unvisited children\n")
        current_level = prev_depth - 1
        level_tables_count = 0
    else:
        print(f"\n{'='*80}")
        print(f"STARTING PROJECT-AWARE LINEAGE TRACE")
        print(f"{'='*80}")
        print(f"Target: {start_table}")
        print(f"Home Project: {home_project}")
        if max_depth > 0:
            print(f"Max Depth: {max_depth} (overrides project-aware limiting)")
        else:
            print(f"Foreign Project Depth Limit: +{foreign_depth_limit}")
        print(f"Location: {location}")
        if checkpoint_file:
            print(f"Checkpoint: {checkpoint_file}")
        print(f"{'='*80}\n")

        visited = set()
        levels = defaultdict(list)
        # (fqn, level, project_for_api, levels_since_foreign_project)
        queue = deque([(start_fqn, 0, project, 0)])

        relationships: Dict[str, Dict] = defaultdict(
            lambda: {'parents': set(), 'children': set(), 'level': None, 'levels_since_foreign': 0}
        )

        current_level = -1
        level_tables_count = 0

    while queue:
        current_fqn, level, current_project, levels_since_foreign = queue.popleft()

        # Apply simple depth limiting if max_depth is set (overrides project-aware logic)
        if max_depth > 0 and level >= max_depth:
            continue

        # Apply project-aware depth limiting (only if max_depth is not set)
        # Once we've left the home project, check if we've exceeded the limit
        if max_depth == 0 and levels_since_foreign > foreign_depth_limit:
            continue

        if current_fqn in visited:
            continue

        # Print level header when we start a new level
        if level != current_level:
            if current_level >= 0:
                print(
                    f"  -> Completed Level {current_level}: {level_tables_count} tables\n")

            current_level = level
            level_tables_count = 0
            if level == 0:
                print(f"Processing Level {level} (Target Table):")
            else:
                print(f"Processing Level {level} (Upstream Dependencies):")

        visited.add(current_fqn)
        relationships[current_fqn]['level'] = level
        relationships[current_fqn]['levels_since_foreign'] = levels_since_foreign

        try:
            table_project, table_dataset, table_name = parse_table_fqn(current_fqn)
        except ValueError:
            continue

        # Determine if this is in a foreign project
        is_foreign_project = table_project != home_project
        foreign_indicator = " [FOREIGN]" if is_foreign_project else ""
        foreign_count_indicator = f" [+{levels_since_foreign}]" if levels_since_foreign > 0 else ""

        table_info = {
            'fqn': current_fqn,
            'project': table_project,
            'dataset': table_dataset,
            'table': table_name,
            'full_name': f"{table_project}.{table_dataset}.{table_name}",
            'level': level,
            'is_foreign_project': is_foreign_project,
            'levels_since_foreign': levels_since_foreign
        }
        levels[level].append(table_info)
        level_tables_count += 1

        print(
            f"  [{level_tables_count}] {table_project}.{table_dataset}.{table_name}{foreign_indicator}{foreign_count_indicator}")

        # Get upstream dependencies
        upstream_fqns = get_upstream_links(
            client, current_fqn, current_project, location)

        if upstream_fqns:
            print(f"      -> Found {len(upstream_fqns)} upstream dependencies")

        # Track relationships and queue children
        for upstream_fqn in upstream_fqns:
            relationships[current_fqn]['children'].add(upstream_fqn)
            relationships[upstream_fqn]['parents'].add(current_fqn)

            if upstream_fqn not in visited:
                try:
                    upstream_project, _, _ = parse_table_fqn(upstream_fqn)

                    # Calculate levels_since_foreign for the child
                    if upstream_project == home_project:
                        # If child is in home project, keep current counter
                        # (don't reset - per user requirement)
                        child_foreign_count = levels_since_foreign
                    else:
                        # Child is in foreign project
                        if levels_since_foreign == 0:
                            # First foreign project encountered, start counting
                            child_foreign_count = 1
                        else:
                            # Already in foreign territory, increment
                            child_foreign_count = levels_since_foreign + 1

                    queue.append((upstream_fqn, level + 1, upstream_project, child_foreign_count))
                except ValueError:
                    continue

    # Print final level completion
    if current_level >= 0:
        print(
            f"  -> Completed Level {current_level}: {level_tables_count} tables\n")

        if checkpoint_file:
            save_checkpoint(
                checkpoint_file,
                visited,
                dict(levels),
                dict(relationships),
                start_table,
                home_project,
                location,
                current_level,
                foreign_depth_limit
            )

    # Add relationship information to each table
    for level_tables in levels.values():
        for table in level_tables:
            table_fqn = table['fqn']
            table['parents'] = list(relationships[table_fqn]['parents'])
            table['children'] = list(relationships[table_fqn]['children'])
            table['upstream_count'] = len(table['children'])

    # Print traversal summary
    total_tables = sum(len(tables) for tables in levels.values())
    foreign_tables = sum(
        1 for tables in levels.values()
        for table in tables
        if table.get('is_foreign_project', False)
    )

    print(f"{'='*80}")
    print(f"TRAVERSAL COMPLETE")
    print(f"{'='*80}")
    print(f"Total tables discovered: {total_tables}")
    print(f"  Home project ({home_project}): {total_tables - foreign_tables}")
    print(f"  Foreign projects: {foreign_tables}")
    print(f"Total levels: {len(levels)}")
    print(f"{'='*80}\n")

    return dict(levels)


def export_to_json(
    levels: Dict[int, List[dict]],
    start_table: str,
    output_file: str,
    location: str,
    home_project: str,
    foreign_depth_limit: int
) -> None:
    """Export lineage graph to JSON file.

    Args:
        levels: Dictionary of levels with table information.
        start_table: Name of the target table.
        output_file: Path to output JSON file.
        location: BigQuery location used.
        home_project: Home project ID.
        foreign_depth_limit: Depth limit for foreign projects.
    """
    project, dataset, table = parse_table_name(start_table)

    # Build relationships list
    relationships = []
    for level_tables in levels.values():
        for table_info in level_tables:
            for child_fqn in table_info.get('children', []):
                child_full_name = None
                for child_level_tables in levels.values():
                    for child_table in child_level_tables:
                        if child_table['fqn'] == child_fqn:
                            child_full_name = child_table['full_name']
                            break
                    if child_full_name:
                        break

                if child_full_name:
                    relationships.append({
                        'source': child_full_name,
                        'target': table_info['full_name'],
                        'level': table_info['level']
                    })

    # Calculate metadata
    total_tables = sum(len(tables) for tables in levels.values())
    max_level = max(levels.keys()) if levels else 0
    foreign_tables = sum(
        1 for tables in levels.values()
        for table in tables
        if table.get('is_foreign_project', False)
    )

    # Build output structure
    output = {
        'target_table': {
            'project': project,
            'dataset': dataset,
            'table': table,
            'full_name': start_table
        },
        'metadata': {
            'total_tables': total_tables,
            'home_project_tables': total_tables - foreign_tables,
            'foreign_project_tables': foreign_tables,
            'total_levels': max_level + 1,
            'max_depth_reached': max_level,
            'home_project': home_project,
            'foreign_depth_limit': foreign_depth_limit,
            'export_timestamp': datetime.now().isoformat(),
            'location': location,
            'traversal_complete': True,
            'truncated_by_project_limit': foreign_tables > 0
        },
        'lineage_by_level': {},
        'relationships': relationships
    }

    # Add tables by level
    for level, tables in sorted(levels.items()):
        output['lineage_by_level'][str(level)] = [
            {
                'full_name': t['full_name'],
                'project': t['project'],
                'dataset': t['dataset'],
                'table': t['table'],
                'upstream_count': t['upstream_count'],
                'is_foreign_project': t.get('is_foreign_project', False),
                'levels_since_foreign': t.get('levels_since_foreign', 0)
            }
            for t in tables
        ]

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Lineage exported to: {output_file}")


def print_lineage_summary(
    levels: Dict[int, List[dict]],
    start_table: str,
    home_project: str
) -> None:
    """Print lineage summary to console.

    Args:
        levels: Dictionary of levels with table information.
        start_table: Name of the target table.
        home_project: Home project ID.
    """
    print(f"\n{'='*80}")
    print(f"COMPLETE LINEAGE FOR: {start_table}")
    print(f"{'='*80}\n")

    max_level = max(levels.keys()) if levels else 0

    for level in sorted(levels.keys()):
        tables = levels[level]

        if level == 0:
            print(f"TARGET TABLE (Level {level}):")
        else:
            print(f"\nUPSTREAM DEPENDENCIES (Level {level}):")

        print("-" * 80)

        # Group by project
        by_project = defaultdict(list)
        for table in tables:
            by_project[table['project']].append(table)

        for proj in sorted(by_project.keys()):
            project_tables = by_project[proj]
            is_foreign = proj != home_project
            foreign_marker = " [FOREIGN]" if is_foreign else " [HOME]"

            if len(by_project) > 1:
                print(
                    f"\n  PROJECT: {proj}{foreign_marker} ({len(project_tables)} tables):")
            else:
                print()

            for table in sorted(project_tables, key=lambda x: x['full_name']):
                indent = "    " if len(by_project) > 1 else "  "
                foreign_count = table.get('levels_since_foreign', 0)
                count_marker = f" [+{foreign_count}]" if foreign_count > 0 else ""
                print(f"{indent}* {table['full_name']}{count_marker}")
                if table['upstream_count'] > 0:
                    print(
                        f"{indent}  Upstream dependencies: {table['upstream_count']}")

    print(f"\n{'='*80}")
    print(f"SUMMARY:")
    print(f"{'='*80}")
    print(f"Total levels: {max_level + 1}")

    total_tables = sum(len(tables) for tables in levels.values())
    print(f"Total tables: {total_tables}")

    # Count tables by project
    project_counts = defaultdict(int)
    for level_tables in levels.values():
        for table in level_tables:
            project_counts[table['project']] += 1

    if len(project_counts) > 1:
        print(f"\nTables by project:")
        for proj, count in sorted(project_counts.items()):
            is_home = " [HOME]" if proj == home_project else ""
            print(f"  {proj}{is_home}: {count}")

    print(f"\n{'='*80}\n")


def generate_tree_view(
    node_id: str,
    levels: Dict[int, List[dict]],
    prefix: str = "",
    is_last: bool = True,
    max_depth: int = 0,
    max_children: int = 0,
    current_depth: int = 0,
    visited: Optional[Set[str]] = None
) -> List[str]:
    """Generate a visual tree view of dependencies.

    Args:
        node_id: Current node ID (full table name).
        levels: Dictionary of levels with node information.
        prefix: Current line prefix for indentation.
        is_last: Whether this is the last child.
        max_depth: Maximum depth to traverse (0 for unlimited).
        max_children: Maximum children to show per node (0 for unlimited).
        current_depth: Current depth in the tree.
        visited: Set of visited nodes to avoid cycles.

    Returns:
        List of formatted tree lines.
    """
    if visited is None:
        visited = set()

    if (max_depth > 0 and current_depth >= max_depth) or node_id in visited:
        return []

    visited.add(node_id)
    lines = []

    # Find node in levels
    node = None
    for level_nodes in levels.values():
        for n in level_nodes:
            if n['full_name'] == node_id or n['fqn'] == node_id:
                node = n
                break
        if node:
            break

    if not node:
        return lines

    # Format node name
    node_name = node['table']
    is_foreign = node.get('is_foreign_project', False)
    foreign_count = node.get('levels_since_foreign', 0)

    if is_foreign and foreign_count > 0:
        node_name = f"{node_name} [+{foreign_count}]"
    elif is_foreign:
        node_name = f"{node_name} [FOREIGN]"

    # Add current node
    connector = "+-- " if is_last else "|-- "
    lines.append(f"{prefix}{connector}{node_name}")

    # Get children
    children = sorted(node.get('children', []))

    should_continue = (max_depth <= 0 or current_depth < max_depth - 1)

    if children and should_continue:
        if max_children > 0:
            children = children[:max_children]

        for idx, child_fqn in enumerate(children):
            # Convert FQN to full_name
            child_id = None
            for level_nodes in levels.values():
                for n in level_nodes:
                    if n['fqn'] == child_fqn:
                        child_id = n['full_name']
                        break
                if child_id:
                    break

            if not child_id:
                continue

            is_last_child = (idx == len(children) - 1)
            extension = "    " if is_last else "|   "
            child_lines = generate_tree_view(
                child_id,
                levels,
                prefix + extension,
                is_last_child,
                max_depth,
                max_children,
                current_depth + 1,
                visited
            )
            lines.extend(child_lines)

    return lines


def write_markdown_report(
    levels: Dict[int, List[dict]],
    target_table: str,
    output_file: str,
    metadata: dict,
    tree_max_depth: int = 0,
    tree_max_children: int = 0
) -> None:
    """Write lineage report to a markdown file.

    Args:
        levels: Dictionary of levels with node information.
        target_table: Name of the target table.
        output_file: Path to output markdown file.
        metadata: Metadata from the lineage export.
        tree_max_depth: Maximum depth for tree view (0 for unlimited).
        tree_max_children: Maximum children per node (0 for unlimited).
    """
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

    with open(output_file, 'w') as f:
        f.write(f"# Lineage Report: {target_table}\n\n")
        f.write(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Add metadata section
        f.write("## Export Metadata\n\n")
        f.write(
            f"- **Export Timestamp:** {metadata.get('export_timestamp', 'N/A')}\n")
        f.write(f"- **Total Tables:** {metadata.get('total_tables', 'N/A')}\n")
        f.write(f"  - Home Project Tables: {metadata.get('home_project_tables', 'N/A')}\n")
        f.write(f"  - Foreign Project Tables: {metadata.get('foreign_project_tables', 'N/A')}\n")
        f.write(f"- **Total Levels:** {metadata.get('total_levels', 'N/A')}\n")
        f.write(
            f"- **Max Depth Reached:** {metadata.get('max_depth_reached', 'N/A')}\n")
        f.write(f"- **Home Project:** {metadata.get('home_project', 'N/A')}\n")
        f.write(f"- **Foreign Project Depth Limit:** +{metadata.get('foreign_depth_limit', 'N/A')}\n")
        f.write(f"- **Location:** {metadata.get('location', 'N/A')}\n")
        f.write(
            f"- **Truncated by Project Limit:** {metadata.get('truncated_by_project_limit', 'N/A')}\n\n")

        max_level = max(levels.keys()) if levels else 0
        total_nodes = sum(len(nodes) for nodes in levels.values())

        # Count tables by project and dataset
        project_counts = defaultdict(int)
        dataset_counts = defaultdict(int)
        for level_nodes in levels.values():
            for node in level_nodes:
                project_counts[node['project']] += 1
                dataset_counts[f"{node['project']}.{node['dataset']}"] += 1

        f.write("## Summary\n\n")
        f.write(f"- **Total Levels:** {max_level + 1}\n")
        f.write(f"- **Total Tables:** {total_nodes}\n\n")

        f.write("### Tables by Project\n\n")
        home_project = metadata.get('home_project', '')
        for project, count in sorted(project_counts.items()):
            marker = " [HOME]" if project == home_project else ""
            f.write(f"- **{project}{marker}:** {count}\n")
        f.write("\n")

        f.write("### Tables by Dataset\n\n")
        for dataset, count in sorted(dataset_counts.items()):
            f.write(f"- **{dataset}:** {count}\n")
        f.write("\n")

        # Add visual tree view
        f.write("## Lineage Tree View\n\n")

        if tree_max_depth <= 0 and tree_max_children <= 0:
            limit_desc = "complete dependency hierarchy (no limits)"
        elif tree_max_depth <= 0:
            limit_desc = f"dependency hierarchy (unlimited depth, max {tree_max_children} children per node)"
        elif tree_max_children <= 0:
            limit_desc = f"dependency hierarchy (max {tree_max_depth} levels deep, unlimited children)"
        else:
            limit_desc = f"dependency hierarchy (max {tree_max_depth} levels deep, max {tree_max_children} children per node)"

        f.write(f"Visual representation of the {limit_desc}:\n\n")
        f.write("Legend: `[FOREIGN]` = foreign project, `[+N]` = N levels since leaving home project\n\n")
        f.write("```\n")

        start_node = levels[0][0]
        tree_lines = generate_tree_view(
            start_node['full_name'], levels, max_depth=tree_max_depth, max_children=tree_max_children)

        for line in tree_lines:
            f.write(f"{line}\n")

        f.write("```\n\n")

        f.write("## Dependency Tree\n\n")

        for level in sorted(levels.keys()):
            nodes = levels[level]

            if level == 0:
                f.write(f"### Level {level}: Target Table\n\n")
            else:
                f.write(f"### Level {level}: Upstream Dependencies\n\n")

            for node in sorted(nodes, key=lambda x: x['full_name']):
                is_foreign = node.get('is_foreign_project', False)
                foreign_count = node.get('levels_since_foreign', 0)
                foreign_marker = f" [FOREIGN +{foreign_count}]" if is_foreign and foreign_count > 0 else (" [FOREIGN]" if is_foreign else "")

                f.write(f"- **{node['full_name']}{foreign_marker}**\n")
                f.write(f"  - Project: `{node['project']}`\n")
                f.write(f"  - Dataset: `{node['dataset']}`\n")
                f.write(f"  - Table: `{node['table']}`\n")

                if node.get('parents'):
                    parent_names = []
                    for parent_fqn in sorted(node['parents']):
                        for level_nodes in levels.values():
                            for parent_node in level_nodes:
                                if parent_node['fqn'] == parent_fqn:
                                    parent_names.append(
                                        f"{parent_node['table']} (Level {parent_node['level']})")
                                    break
                    if parent_names:
                        f.write(f"  - **Used by:** {', '.join(parent_names)}\n")

                if node.get('children'):
                    child_names = []
                    for child_fqn in sorted(node['children']):
                        for level_nodes in levels.values():
                            for child_node in level_nodes:
                                if child_node['fqn'] == child_fqn:
                                    child_names.append(
                                        f"{child_node['table']} (Level {child_node['level']})")
                                    break
                    if child_names:
                        f.write(
                            f"  - **Depends on:** {', '.join(child_names)}\n")

                f.write("\n")

    print(f"Markdown report written to: {output_file}")


def main():
    """Main entry point for the project-aware lineage analyzer."""
    parser = argparse.ArgumentParser(
        description='Analyze BigQuery table lineage with project-aware depth limiting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze lineage with +3 foreign project depth (default)
  python analyze_bq_lineage.py project.dataset.table

  # Simple depth limiting: only 2 levels total (overrides project-aware logic)
  python analyze_bq_lineage.py project.dataset.table --max-depth 2

  # Export to specific file with all outputs
  python analyze_bq_lineage.py project.dataset.table --file lineage.json

  # Limit to +5 levels after leaving home project
  python analyze_bq_lineage.py project.dataset.table --foreign-project-depth 5

  # JSON output only
  python analyze_bq_lineage.py project.dataset.table -o json

  # Specify BigQuery location
  python analyze_bq_lineage.py project.dataset.table --location eu

  # Use output directory from config
  python analyze_bq_lineage.py project.dataset.table --output-dir auto
        """
    )

    parser.add_argument(
        'table_name',
        help='Fully qualified table name (project.dataset.table)'
    )
    parser.add_argument(
        '--location',
        default='us',
        help='BigQuery location/region (default: us)'
    )
    parser.add_argument(
        '--foreign-project-depth',
        type=int,
        default=3,
        help='Levels to traverse after leaving home project (default: 3)'
    )
    parser.add_argument(
        '--max-depth',
        type=int,
        default=0,
        help='Maximum depth to traverse, overrides project-aware limiting (0 for project-aware, default: 0)'
    )
    parser.add_argument(
        '-o', '--output-format',
        choices=['json', 'console', 'markdown', 'both', 'all'],
        default='all',
        help='Output format (default: all - json, console, and markdown)'
    )
    parser.add_argument(
        '-f', '--file',
        help='Output JSON file path (default: lineage_bq_<table>.json)'
    )
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory (use "auto" to read from config, default: current directory)'
    )
    parser.add_argument(
        '--checkpoint',
        help='Save checkpoint to this file after each level (enables resume)'
    )
    parser.add_argument(
        '--resume',
        help='Resume from checkpoint file (continues from previous depth)'
    )
    parser.add_argument(
        '-c', '--config',
        default='config/migration_config.yaml',
        help='Path to configuration file (default: config/migration_config.yaml)'
    )

    args = parser.parse_args()

    # Determine output directory
    output_dir = args.output_dir
    if output_dir == "auto" or output_dir is None:
        if CONFIG_AVAILABLE and os.path.exists(args.config):
            try:
                config = load_config(args.config)
                output_dir = get_config_value(
                    config, "outputs.lineage", "lineage_analyzer/outputs")
                print(f"Configuration loaded from: {args.config}")
                print(f"Output directory: {output_dir}")
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
                output_dir = "."
        else:
            output_dir = "."

    # Validate table name format
    try:
        project, dataset, table = parse_table_name(args.table_name)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Initialize client
    try:
        client = get_lineage_client(args.location)
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure you have:")
        print("1. Installed: pip install google-cloud-datacatalog-lineage")
        print("2. Authenticated: gcloud auth application-default login")
        print("3. Enabled Data Lineage API in your GCP project")
        sys.exit(1)

    # Trace lineage
    levels = trace_lineage_with_project_limit(
        client,
        args.table_name,
        args.location,
        args.foreign_project_depth,
        args.max_depth,
        checkpoint_file=args.checkpoint,
        resume_checkpoint=args.resume
    )

    if not levels:
        print("No lineage found for the specified table.")
        print("\nPossible reasons:")
        print("1. Data Lineage API is not enabled in the project")
        print("2. No queries have been executed on this table since lineage was enabled")
        print("3. The table does not exist")
        print("4. You don't have permission to access lineage data")
        sys.exit(1)

    # Output results
    output_format = args.output_format

    # Handle 'both' (json + console) and 'all' (json + console + markdown)
    show_console = output_format in ['console', 'both', 'all']
    save_json = output_format in ['json', 'both', 'all']
    save_markdown = output_format in ['markdown', 'all']

    if show_console:
        print_lineage_summary(levels, args.table_name, project)

    if save_json:
        json_file = args.file or os.path.join(output_dir, f"lineage_bq_{table}.json")
        export_to_json(
            levels,
            args.table_name,
            json_file,
            args.location,
            project,
            args.foreign_project_depth
        )

    if save_markdown:
        # Build metadata for markdown
        total_tables = sum(len(tables) for tables in levels.values())
        max_level = max(levels.keys()) if levels else 0
        foreign_tables = sum(
            1 for tables in levels.values()
            for table_info in tables
            if table_info.get('is_foreign_project', False)
        )

        metadata = {
            'total_tables': total_tables,
            'home_project_tables': total_tables - foreign_tables,
            'foreign_project_tables': foreign_tables,
            'total_levels': max_level + 1,
            'max_depth_reached': max_level,
            'home_project': project,
            'foreign_depth_limit': args.foreign_project_depth,
            'export_timestamp': datetime.now().isoformat(),
            'location': args.location,
            'traversal_complete': True,
            'truncated_by_project_limit': foreign_tables > 0
        }

        md_file = os.path.join(output_dir, f"lineage_bq_{table}.md")
        write_markdown_report(
            levels,
            args.table_name,
            md_file,
            metadata,
            tree_max_depth=0,  # Unlimited depth for complete tree
            tree_max_children=0  # Unlimited children
        )


if __name__ == "__main__":
    main()
