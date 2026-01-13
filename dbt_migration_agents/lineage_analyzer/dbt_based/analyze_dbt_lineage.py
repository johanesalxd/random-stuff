#!/usr/bin/env python3
"""Analyze dbt model lineage from manifest.json.

This module traces all dependencies from a target model to upstream sources,
providing comprehensive lineage analysis for dbt projects.

Configuration:
    Optionally reads from config/migration_config.yaml for:
    - project.manifest_path: Path to DBT manifest
    - outputs.lineage: Output directory for lineage files
"""

import argparse
from collections import defaultdict
from collections import deque
from datetime import datetime
import json
import os
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


def load_manifest(manifest_path: str = "target/manifest.json") -> dict:
    """Load and parse the dbt manifest.json file.

    Args:
        manifest_path: Path to the manifest.json file.

    Returns:
        Parsed manifest as a dictionary.

    Raises:
        FileNotFoundError: If manifest file does not exist.
        json.JSONDecodeError: If manifest file is not valid JSON.
    """
    try:
        with open(manifest_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Manifest file not found at {manifest_path}. "
            "Run 'dbt docs generate' first."
        )
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in manifest file: {e.msg}",
            e.doc,
            e.pos
        )


def merge_manifests(manifests: List[dict]) -> dict:
    """Merge multiple dbt manifests into a unified manifest.

    When merging, nodes from later manifests take precedence. This allows
    downstream projects to reference upstream models as sources, which will
    be resolved to the actual upstream models.

    Args:
        manifests: List of manifest dictionaries to merge.

    Returns:
        Merged manifest dictionary with unified nodes and sources.
    """
    if not manifests:
        return {}

    if len(manifests) == 1:
        return manifests[0]

    merged = {
        'nodes': {},
        'sources': {},
        'metadata': manifests[0].get('metadata', {}),
    }

    # Merge all manifests
    for manifest in manifests:
        # Merge nodes
        for node_id, node in manifest.get('nodes', {}).items():
            merged['nodes'][node_id] = node

        # Merge sources
        for source_id, source in manifest.get('sources', {}).items():
            merged['sources'][source_id] = source

    # Resolve cross-project references:
    # If a "source" in the downstream project matches a "model" in upstream,
    # update dependencies to point to the actual model instead of the source
    source_to_model_map = {}

    # Build mapping: source name -> model node_id
    for node_id, node in merged['nodes'].items():
        if node.get('resource_type') == 'model':
            model_name = node.get('name')
            database = node.get('database', '')
            schema = node.get('schema', '')

            # Create lookup key from database.schema.name
            lookup_key = f"{database}.{schema}.{model_name}"
            source_to_model_map[lookup_key] = node_id

    # Track which sources have been resolved to models
    resolved_source_ids = set()

    # Update dependencies in all nodes
    for node_id, node in merged['nodes'].items():
        depends_on = node.get('depends_on', {})
        updated_nodes = []
        updated_sources = []

        # Check each source dependency
        for source_id in depends_on.get('sources', []):
            source = merged['sources'].get(source_id)
            if source:
                source_name = source.get('name')
                database = source.get('database', '')
                schema = source.get('schema', '')
                lookup_key = f"{database}.{schema}.{source_name}"

                # If this source matches an upstream model, use the model instead
                if lookup_key in source_to_model_map:
                    model_id = source_to_model_map[lookup_key]
                    updated_nodes.append(model_id)
                    resolved_source_ids.add(source_id)
                else:
                    updated_sources.append(source_id)
            else:
                updated_sources.append(source_id)

        # Keep existing node dependencies
        updated_nodes.extend(depends_on.get('nodes', []))

        # Update the depends_on structure
        node['depends_on']['nodes'] = updated_nodes
        node['depends_on']['sources'] = updated_sources

    # Remove resolved sources from the sources dictionary
    # This ensures they are only retrieved as models during lineage tracing
    for source_id in resolved_source_ids:
        if source_id in merged['sources']:
            del merged['sources'][source_id]

    return merged


def find_node(manifest: dict, model_name: str) -> Tuple[Optional[str], Optional[dict]]:
    """Find a node in the manifest by model name.

    Args:
        manifest: The dbt manifest dictionary.
        model_name: Name of the model to find.

    Returns:
        Tuple of (node_id, node_dict) if found, (None, None) otherwise.
    """
    for node_id, node in manifest.get('nodes', {}).items():
        if node.get('name') == model_name or node.get('alias') == model_name:
            return node_id, node

    for source_id, source in manifest.get('sources', {}).items():
        if source.get('name') == model_name:
            return source_id, source

    return None, None


def get_node_info(manifest: dict, node_id: str) -> Optional[dict]:
    """Get node information from manifest.

    Args:
        manifest: The dbt manifest dictionary.
        node_id: Unique identifier for the node.

    Returns:
        Node dictionary if found, None otherwise.
    """
    if node_id in manifest.get('nodes', {}):
        return manifest['nodes'][node_id]

    if node_id in manifest.get('sources', {}):
        return manifest['sources'][node_id]

    return None


def get_dependencies(node: dict) -> List[str]:
    """Extract dependencies from a node.

    Args:
        node: Node dictionary from manifest.

    Returns:
        List of dependency node IDs.
    """
    if not node:
        return []

    depends_on = node.get('depends_on', {})
    deps = []
    deps.extend(depends_on.get('nodes', []))
    deps.extend(depends_on.get('sources', []))

    return deps


def trace_lineage(manifest: dict, start_model: str) -> Dict[int, List[dict]]:
    """Trace complete lineage from start_model to all upstream sources.

    Uses breadth-first search to traverse the dependency graph and organize
    nodes by their distance (level) from the target model.

    Args:
        manifest: The dbt manifest dictionary.
        start_model: Name of the model to trace lineage for.

    Returns:
        Dictionary with levels as keys and list of node info dicts as values.
        Returns empty dict if model not found.
    """
    start_node_id, start_node = find_node(manifest, start_model)

    if not start_node_id:
        print(f"Error: Model '{start_model}' not found in manifest")
        return {}

    visited = set()
    levels = defaultdict(list)
    queue = deque([(start_node_id, 0)])

    # Track relationships: node_id -> {parents: set, children: set, level: int}
    relationships = defaultdict(
        lambda: {'parents': set(), 'children': set(), 'level': None})

    while queue:
        node_id, level = queue.popleft()

        if node_id in visited:
            continue

        visited.add(node_id)
        relationships[node_id]['level'] = level

        node = get_node_info(manifest, node_id)
        if not node:
            continue

        node_type = node.get('resource_type', 'unknown')
        node_name = node.get('name', 'unknown')
        node_path = node.get('original_file_path', node.get('path', 'N/A'))

        levels[level].append({
            'id': node_id,
            'name': node_name,
            'type': node_type,
            'path': node_path,
            'database': node.get('database', 'N/A'),
            'schema': node.get('schema', 'N/A'),
        })

        deps = get_dependencies(node)
        for dep_id in deps:
            # Track parent-child relationships
            relationships[node_id]['children'].add(dep_id)
            relationships[dep_id]['parents'].add(node_id)

            if dep_id not in visited:
                queue.append((dep_id, level + 1))

    # Add relationship information to each node
    for level_nodes in levels.values():
        for node in level_nodes:
            node_id = node['id']
            node['parents'] = relationships[node_id]['parents']
            node['children'] = relationships[node_id]['children']

    return dict(levels)


def get_node_name_and_level(node_id: str, levels: Dict[int, List[dict]]) -> Tuple[str, int]:
    """Get node name and level from node ID.

    Args:
        node_id: The node ID to look up.
        levels: Dictionary of levels with node information.

    Returns:
        Tuple of (node_name, level). Returns ('unknown', -1) if not found.
    """
    for level, nodes in levels.items():
        for node in nodes:
            if node['id'] == node_id:
                return node['name'], level
    return 'unknown', -1


def get_node_by_id(node_id: str, levels: Dict[int, List[dict]]) -> Optional[dict]:
    """Get node dictionary by node ID.

    Args:
        node_id: The node ID to look up.
        levels: Dictionary of levels with node information.

    Returns:
        Node dictionary if found, None otherwise.
    """
    for nodes in levels.values():
        for node in nodes:
            if node['id'] == node_id:
                return node
    return None


def generate_tree_view(
    node_id: str,
    levels: Dict[int, List[dict]],
    prefix: str = "",
    is_last: bool = True,
    max_depth: int = 5,
    max_children: int = 10,
    current_depth: int = 0,
    visited: Optional[Set[str]] = None
) -> List[str]:
    """Generate a visual tree view of dependencies.

    Args:
        node_id: Current node ID.
        levels: Dictionary of levels with node information.
        prefix: Current line prefix for indentation.
        is_last: Whether this is the last child.
        max_depth: Maximum depth to traverse (0 or negative for unlimited).
        max_children: Maximum children to show per node (0 or negative for unlimited).
        current_depth: Current depth in the tree.
        visited: Set of visited nodes to avoid cycles.

    Returns:
        List of formatted tree lines.
    """
    if visited is None:
        visited = set()

    # Check depth limit (0 or negative means unlimited)
    if (max_depth > 0 and current_depth >= max_depth) or node_id in visited:
        return []

    visited.add(node_id)
    lines = []

    node = get_node_by_id(node_id, levels)
    if not node:
        return lines

    # Format node name with type indicator
    node_name = node['name']
    if node['type'] in ['source', 'seed']:
        node_name = f"{node_name} ({node['type'].upper()})"

    # Add current node
    connector = "└── " if is_last else "├── "
    lines.append(f"{prefix}{connector}{node_name}")

    # Get children
    children = sorted(node.get('children', set()))

    # Check if we should continue (depth limit check)
    should_continue = (max_depth <= 0 or current_depth < max_depth - 1)

    if children and should_continue:
        # Limit children if max_children is set (0 or negative means unlimited)
        if max_children > 0:
            children = children[:max_children]

        for idx, child_id in enumerate(children):
            is_last_child = (idx == len(children) - 1)
            extension = "    " if is_last else "│   "
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
    start_model: str,
    output_file: str,
    tree_max_depth: int = 5,
    tree_max_children: int = 10
) -> None:
    """Write lineage report to a markdown file.

    Args:
        levels: Dictionary of levels with node information.
        start_model: Name of the target model.
        output_file: Path to output markdown file.
        tree_max_depth: Maximum depth for tree view (0 for unlimited).
        tree_max_children: Maximum children per node (0 for unlimited).
    """
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

    with open(output_file, 'w') as f:
        f.write(f"# Lineage Report: {start_model}\n\n")
        f.write(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        max_level = max(levels.keys()) if levels else 0
        total_nodes = sum(len(nodes) for nodes in levels.values())

        type_counts = defaultdict(int)
        for level_nodes in levels.values():
            for node in level_nodes:
                type_counts[node['type']] += 1

        f.write("## Summary\n\n")
        f.write(f"- **Total Levels:** {max_level + 1}\n")
        f.write(f"- **Total Nodes:** {total_nodes}\n\n")

        f.write("### Nodes by Type\n\n")
        for node_type, count in sorted(type_counts.items()):
            f.write(f"- **{node_type.title()}:** {count}\n")
        f.write("\n")

        # Add visual tree view
        f.write("## Lineage Tree View\n\n")

        # Build description based on limits
        if tree_max_depth <= 0 and tree_max_children <= 0:
            limit_desc = "complete dependency hierarchy (no limits)"
        elif tree_max_depth <= 0:
            limit_desc = f"dependency hierarchy (unlimited depth, max {tree_max_children} children per node)"
        elif tree_max_children <= 0:
            limit_desc = f"dependency hierarchy (max {tree_max_depth} levels deep, unlimited children)"
        else:
            limit_desc = f"dependency hierarchy (max {tree_max_depth} levels deep, max {tree_max_children} children per node)"

        f.write(f"Visual representation of the {limit_desc}:\n\n")
        f.write("```\n")

        start_node = levels[0][0]
        tree_lines = generate_tree_view(
            start_node['id'], levels, max_depth=tree_max_depth, max_children=tree_max_children)

        for line in tree_lines:
            f.write(f"{line}\n")

        f.write("```\n\n")

        f.write("## Dependency Tree\n\n")

        for level in sorted(levels.keys()):
            nodes = levels[level]

            if level == 0:
                f.write(f"### Level {level}: Target Model\n\n")
            else:
                f.write(f"### Level {level}: Upstream Dependencies\n\n")

            by_type = defaultdict(list)
            for node in nodes:
                by_type[node['type']].append(node)

            for node_type in sorted(by_type.keys()):
                type_nodes = by_type[node_type]
                f.write(f"#### {node_type.upper()} ({len(type_nodes)})\n\n")

                for node in sorted(type_nodes, key=lambda x: x['name']):
                    f.write(f"- **{node['name']}**\n")
                    f.write(f"  - Path: `{node['path']}`\n")
                    if node['database'] != 'N/A':
                        f.write(
                            f"  - Location: `{node['database']}.{node['schema']}`\n")

                    # Add relationship information
                    if node.get('parents'):
                        parent_info = []
                        for parent_id in sorted(node['parents']):
                            parent_name, parent_level = get_node_name_and_level(
                                parent_id, levels)
                            parent_info.append(
                                f"{parent_name} (Level {parent_level})")
                        f.write(f"  - **Used by:** {', '.join(parent_info)}\n")

                    if node.get('children'):
                        child_info = []
                        for child_id in sorted(node['children']):
                            child_name, child_level = get_node_name_and_level(
                                child_id, levels)
                            child_info.append(
                                f"{child_name} (Level {child_level})")
                        f.write(
                            f"  - **Depends on:** {', '.join(child_info)}\n")

                    f.write("\n")

        sources = []
        seeds = []
        for level_nodes in levels.values():
            for node in level_nodes:
                if node['type'] == 'source':
                    sources.append(node)
                elif node['type'] == 'seed':
                    seeds.append(node)

        f.write("## Most Upstream Sources\n\n")

        if sources:
            f.write(f"### External Sources ({len(sources)})\n\n")
            for source in sorted(sources, key=lambda x: x['name']):
                f.write(f"- **{source['name']}**\n")
                f.write(
                    f"  - Location: `{source['database']}.{source['schema']}`\n")
                f.write("\n")

        if seeds:
            f.write(f"### Seed Files ({len(seeds)})\n\n")
            for seed in sorted(seeds, key=lambda x: x['name']):
                f.write(f"- **{seed['name']}**\n")
                f.write(f"  - Path: `{seed['path']}`\n")
                f.write("\n")

    print(f"\nMarkdown report written to: {output_file}")


def print_lineage_tree(levels: Dict[int, List[dict]], start_model: str) -> None:
    """Print lineage in a tree format to console.

    Args:
        levels: Dictionary of levels with node information.
        start_model: Name of the target model.
    """
    print(f"\n{'='*80}")
    print(f"COMPLETE LINEAGE FOR: {start_model}")
    print(f"{'='*80}\n")

    max_level = max(levels.keys()) if levels else 0

    for level in sorted(levels.keys()):
        nodes = levels[level]

        if level == 0:
            print(f"TARGET MODEL (Level {level}):")
        else:
            print(f"\nUPSTREAM DEPENDENCIES (Level {level}):")

        print("-" * 80)

        by_type = defaultdict(list)
        for node in nodes:
            by_type[node['type']].append(node)

        for node_type in sorted(by_type.keys()):
            type_nodes = by_type[node_type]
            print(f"\n  {node_type.upper()} ({len(type_nodes)}):")

            for node in sorted(type_nodes, key=lambda x: x['name']):
                indent = "    "
                print(f"{indent}* {node['name']}")
                print(f"{indent}  Path: {node['path']}")
                if node['database'] != 'N/A':
                    print(
                        f"{indent}  Location: {node['database']}.{node['schema']}")

    print(f"\n{'='*80}")
    print(f"SUMMARY:")
    print(f"{'='*80}")
    print(f"Total levels: {max_level + 1}")

    total_nodes = sum(len(nodes) for nodes in levels.values())
    print(f"Total nodes: {total_nodes}")

    type_counts = defaultdict(int)
    for level_nodes in levels.values():
        for node in level_nodes:
            type_counts[node['type']] += 1

    print(f"\nNodes by type:")
    for node_type, count in sorted(type_counts.items()):
        print(f"  {node_type}: {count}")

    print(f"\n{'='*80}\n")


def print_upstream_sources(levels: Dict[int, List[dict]]) -> None:
    """Print only the most upstream sources (sources and seeds).

    Args:
        levels: Dictionary of levels with node information.
    """
    print(f"\n{'='*80}")
    print(f"MOST UPSTREAM SOURCES:")
    print(f"{'='*80}\n")

    sources = []
    seeds = []

    for level_nodes in levels.values():
        for node in level_nodes:
            if node['type'] == 'source':
                sources.append(node)
            elif node['type'] == 'seed':
                seeds.append(node)

    if sources:
        print(f"EXTERNAL SOURCES ({len(sources)}):")
        print("-" * 80)
        for source in sorted(sources, key=lambda x: x['name']):
            print(f"  * {source['name']}")
            print(f"    Location: {source['database']}.{source['schema']}")
            print()

    if seeds:
        print(f"\nSEED FILES ({len(seeds)}):")
        print("-" * 80)
        for seed in sorted(seeds, key=lambda x: x['name']):
            print(f"  * {seed['name']}")
            print(f"    Path: {seed['path']}")
            print()

    print(f"{'='*80}\n")


def main():
    """Main entry point for the lineage analyzer."""
    parser = argparse.ArgumentParser(
        description='Analyze dbt model lineage from manifest.json',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze lineage for a single model
  python analyze_dbt_lineage.py my_model

  # Use specific manifest file
  python analyze_dbt_lineage.py my_model -m target/manifest.json

  # Output to markdown file
  python analyze_dbt_lineage.py my_model -o markdown -f lineage_output.md

  # Multiple manifests for cross-project lineage
  python analyze_dbt_lineage.py my_model -m upstream/target/manifest.json downstream/target/manifest.json
        """
    )
    parser.add_argument(
        'model_name',
        help='Name of the model to analyze'
    )
    parser.add_argument(
        '-m', '--manifests',
        nargs='+',
        help='Paths to manifest.json files (default: from config or target/manifest.json). '
             'For cross-project lineage, provide upstream manifests first, '
             'then downstream manifests.'
    )
    parser.add_argument(
        '-o', '--output',
        choices=['console', 'markdown', 'both'],
        default='both',
        help='Output format (default: both)'
    )
    parser.add_argument(
        '-f', '--file',
        help='Output file path for markdown (default: lineage_dbt_<model_name>.md)'
    )
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory (default: from config or current directory)'
    )
    parser.add_argument(
        '-c', '--config',
        default='config/migration_config.yaml',
        help='Path to configuration file (default: config/migration_config.yaml)'
    )
    parser.add_argument(
        '--tree-depth',
        type=int,
        default=0,
        help='Maximum depth for tree view (0 for unlimited, default: 0)'
    )
    parser.add_argument(
        '--tree-max-children',
        type=int,
        default=0,
        help='Maximum children per node in tree view (0 for unlimited, default: 0)'
    )

    args = parser.parse_args()

    # Load configuration if available
    manifest_paths = args.manifests
    output_dir = args.output_dir

    if CONFIG_AVAILABLE and os.path.exists(args.config):
        try:
            config = load_config(args.config)
            if not manifest_paths:
                default_manifest = get_config_value(
                    config, "project.manifest_path", "target/manifest.json"
                )
                manifest_paths = [default_manifest]
            if not output_dir:
                output_dir = get_config_value(
                    config, "outputs.lineage", "lineage_analyzer/outputs"
                )
            print(f"Configuration loaded from: {args.config}")
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
            manifest_paths = manifest_paths or ['target/manifest.json']
            output_dir = output_dir or "."
    else:
        manifest_paths = manifest_paths or ['target/manifest.json']
        output_dir = output_dir or "."

    # Load all manifests
    manifests = []
    for path in manifest_paths:
        print(f"Loading manifest from {path}...")
        try:
            manifest = load_manifest(path)
            manifests.append(manifest)
            print(f"  Loaded {len(manifest.get('nodes', {}))} nodes and "
                  f"{len(manifest.get('sources', {}))} sources")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading {path}: {e}")
            sys.exit(1)

    # Merge manifests if multiple provided
    if len(manifests) > 1:
        print(f"\nMerging {len(manifests)} manifests...")
        manifest = merge_manifests(manifests)
        print(f"  Merged manifest contains {len(manifest.get('nodes', {}))} nodes and "
              f"{len(manifest.get('sources', {}))} sources")
    else:
        manifest = manifests[0]

    print(f"\nTracing lineage for '{args.model_name}'...")
    levels = trace_lineage(manifest, args.model_name)

    if not levels:
        sys.exit(1)

    if args.output in ['console', 'both']:
        print_lineage_tree(levels, args.model_name)
        print_upstream_sources(levels)

    if args.output in ['markdown', 'both']:
        output_file = args.file or os.path.join(
            output_dir, f"lineage_dbt_{args.model_name}.md"
        )
        write_markdown_report(
            levels,
            args.model_name,
            output_file,
            tree_max_depth=args.tree_depth,
            tree_max_children=args.tree_max_children
        )


if __name__ == "__main__":
    main()
