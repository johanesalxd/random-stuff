# AI Agent Tools

Coding standards and context management for AI-assisted development using Cline.

## Contents

- **AGENTS.md** - Coding standards based on Google style guides (Python, Go, Java, JavaScript/TypeScript, Shell)
- **MEMORY_BANK.md** - Context management guidelines for complex projects
- **cline_gemini_mcp/** - BigQuery MCP server configurations for Cline

## Global Rules Configuration

Cline uses two global rule files that apply to all projects:

- `~/Documents/Cline/Rules/AGENTS.md` - Coding standards
- `~/Documents/Cline/Rules/MEMORY_BANK.md` - Context management

### Setup

```bash
# Protect files from accidental modification
chmod 444 ~/Documents/Cline/Rules/*.md
```

### Usage

```bash
# Start all tasks with
"Follow guidelines in ~/Documents/Cline/Rules/"

# Optional: Initialize Memory Bank for complex projects
"Initialize memory bank"
```

### Memory Bank (Optional)

Use for complex projects requiring context across multiple sessions:

- ✅ Multi-session projects
- ✅ Complex codebases
- ❌ Simple scripts
- ❌ One-off tasks

Memory Bank creates a `memory-bank/` folder with project context files.

## Rules Synchronization

Files in this directory must be kept synchronized with global Cline rules:

**File Locations:**
- Global: `~/Documents/Cline/Rules/AGENTS.md` and `MEMORY_BANK.md`
- Local: `agent_stuff/AGENTS.md` and `MEMORY_BANK.md`

**Protection:**
Set global files to read-only (chmod 444) to prevent accidental modification.

**Update Process:**
When updating standards, modify the local/source files in this directory, then sync to global location and re-apply permissions.

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
