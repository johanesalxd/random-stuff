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

## Shell Integration

Add the following aliases to your `.zshrc` or `.bashrc` for quick access to management scripts:

```bash
# Docker SSH Tunnel Management
export DOCKER_HOST=tcp://localhost:2375
alias manage-docker='~/Developer/git/random-stuff/remote_docker/manage_docker_tunnel.sh'

# Cline MCP Management
alias manage-mcp='~/Developer/git/random-stuff/agent_stuff/cline_gemini_mcp/manage_mcp_servers.sh'
```

**Usage:**
- `manage-docker`: Start, stop, or check status of Docker SSH tunnel
- `manage-mcp`: Manage Cline MCP server configurations

## Important Notes

### Agent Rules Synchronization

The `agent_stuff/AGENTS.md` file in this repository must be kept synchronized with the global Cline rules file located at `~/Documents/Cline/Rules/AGENTS.md`. These files should always contain identical content to ensure consistent coding standards across all projects.

**File Locations:**
- Global: `~/Documents/Cline/Rules/AGENTS.md`
- Local: `agent_stuff/AGENTS.md`

When updating coding standards, both files must be updated to maintain alignment.
