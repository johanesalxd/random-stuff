# BigQuery Toolbox MCP Servers

Quick reference guide for managing BigQuery Toolbox MCP servers (from [Gemini CLI extensions](https://cloud.google.com/bigquery/docs/develop-with-gemini-cli)) for Cline.

## Overview

Two MCP servers provide BigQuery functionality:
- **bigquery-conversational-analytics** (port 5001) - AI-powered data insights
- **bigquery-data-analytics** (port 5002) - Comprehensive BigQuery operations

## Quick Start

Use the provided shell script for easy management:

```bash
# Start servers
./manage_mcp_servers.sh start

# Stop servers
./manage_mcp_servers.sh stop

# Check status
./manage_mcp_servers.sh status

# View logs
./manage_mcp_servers.sh logs
```

## Cline Configuration

The MCP servers are configured in Cline via SSE transport. Configuration file location:
```
~/.vscode-server/data/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
```

Reference configuration is available in `agent_rules/cline_mcp_settings.json`.
