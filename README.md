# Random Stuff

A collection of random, ad-hoc code and projects built over time.

## Project Structure

```
random-stuff/
├── agent_rules/                  # Coding and documentation standards for AI-generated code
│   └── AGENTS.md                 # Comprehensive guidelines based on Google style guides
└── bq_kubernetes_comparison/     # Visual comparison of BigQuery and Kubernetes workload management strategies
    ├── comparison.md             # Mermaid diagram source comparing resource allocation approaches
    └── test_diagram.html         # Interactive HTML viewer for the comparison diagram
```

## Projects

- **agent_rules**: Contains coding and documentation standards for all AI-generated code, based on Google's official style guides for Python, Go, and Java
- **bq_kubernetes_comparison**: Illustrates the analogy between Kubernetes cluster/node management and BigQuery reservation/slot allocation through an interactive diagram

## Important Notes

### Agent Rules Synchronization

The `agent_rules/AGENTS.md` file in this repository must be kept synchronized with the global Cline rules file located at `~/Documents/Cline/Rules/AGENTS.md`. These files should always contain identical content to ensure consistent coding standards across all projects.

**File Locations:**
- Global: `~/Documents/Cline/Rules/AGENTS.md`
- Local: `agent_rules/AGENTS.md`

When updating coding standards, both files must be updated to maintain alignment.
