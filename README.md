# Random Stuff

A collection of random, ad-hoc code and projects built over time.

## Project Structure

```
random-stuff/
├── agent_stuff/
│   ├── AGENTS.md                           # Coding standards for AI-generated code
│   └── cline_gemini_mcp/                   # BigQuery MCP server management for Cline
├── bq_kubernetes_comparison/               # BigQuery vs Kubernetes resource management comparison
└── remote_docker/                          # Docker SSH tunnel management
```

## Projects

- **agent_stuff**: Coding standards based on Google style guides and Cline MCP server configurations
- **bq_kubernetes_comparison**: Visual comparison of BigQuery and Kubernetes workload management strategies
- **remote_docker**: SSH tunnel management for remote Docker daemon access

## Important Notes

### Agent Rules Synchronization

The `agent_stuff/AGENTS.md` file in this repository must be kept synchronized with the global Cline rules file located at `~/Documents/Cline/Rules/AGENTS.md`. These files should always contain identical content to ensure consistent coding standards across all projects.

**File Locations:**
- Global: `~/Documents/Cline/Rules/AGENTS.md`
- Local: `agent_stuff/AGENTS.md`

When updating coding standards, both files must be updated to maintain alignment.
