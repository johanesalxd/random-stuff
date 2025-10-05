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

## AI Agent Configuration

Cline uses two global rule files:
- `~/Documents/Cline/Rules/AGENTS.md` - Coding standards
- `~/Documents/Cline/Rules/MEMORY_BANK.md` - Context management

**Setup:**
```bash
# Protect files from accidental modification
chmod 444 ~/Documents/Cline/Rules/*.md
```

**Usage:**
```bash
# Start all tasks with
"Follow guidelines in ~/Documents/Cline/Rules/"

# Optional: Initialize Memory Bank for complex projects
"Initialize memory bank"
```

**Memory Bank (Optional):**
Use for complex projects requiring context across multiple sessions:
- ✅ Multi-session projects
- ✅ Complex codebases
- ❌ Simple scripts
- ❌ One-off tasks

Memory Bank creates a `memory-bank/` folder with project context files.

## Important Notes

### Agent Rules Synchronization

Files in `agent_stuff/` must be kept synchronized with global Cline rules:

**File Locations:**
- Global: `~/Documents/Cline/Rules/AGENTS.md` and `MEMORY_BANK.md`
- Local: `agent_stuff/AGENTS.md` and `MEMORY_BANK.md`

**Protection:**
Set global files to read-only (chmod 444) to prevent accidental modification.

When updating standards, modify the local/source files, then sync and re-apply permissions.
