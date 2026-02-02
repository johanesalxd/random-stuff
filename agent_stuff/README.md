# AI Agent Tools

Standards and configurations for AI-assisted development using Cline, Claude Code, opencode, and other AI coding agents.

## Contents

| File | Purpose |
|------|---------|
| **AGENTS.md** | Agent behavioral directives (planning, verification, learning loops) |
| **CODE_STANDARDS.md** | Coding style guide based on Google standards (Python, Go, Java, JS/TS, Shell) |
| **cline_gemini_mcp/** | BigQuery MCP server configurations for Cline |

## File Separation Rationale

The agent instructions are split into two files:

- **AGENTS.md** (~40 lines) - How the AI should behave and work
- **CODE_STANDARDS.md** (~600 lines) - How the output code should look

This separation provides:
1. Context window efficiency - agent reads compact directives first
2. Portability - CODE_STANDARDS.md can be shared with human developers and CI pipelines
3. Maintenance - update coding standards without touching agent behavior
4. Tool compatibility - works with Cline, Claude Code, opencode, Cursor, etc.

## Global Rules Configuration

Cline uses global rule files that apply to all projects:

```
~/Documents/Cline/Rules/
├── AGENTS.md          # Agent behavior
└── CODE_STANDARDS.md  # Coding style (optional, can be project-specific)
```

### Setup

```bash
# Copy files to global location
cp agent_stuff/AGENTS.md ~/Documents/Cline/Rules/
cp agent_stuff/CODE_STANDARDS.md ~/Documents/Cline/Rules/

# Protect files from accidental modification
chmod 444 ~/Documents/Cline/Rules/*.md
```

### Synchronization

When updating standards:
1. Modify source files in this directory
2. Sync to global location: `cp agent_stuff/*.md ~/Documents/Cline/Rules/`
3. Re-apply permissions: `chmod 444 ~/Documents/Cline/Rules/*.md`

## MCP Server Management

The `cline_gemini_mcp/` directory contains BigQuery MCP server configurations.

**Shell Alias:**
```bash
alias manage-mcp='~/Developer/git/random-stuff/agent_stuff/cline_gemini_mcp/manage_mcp_servers.sh'
```

**Usage:**
```bash
manage-mcp  # Manage Cline MCP server configurations
```

See `cline_gemini_mcp/README.md` for detailed configuration instructions.
