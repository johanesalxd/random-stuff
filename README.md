# Random Stuff

A collection of random, ad-hoc code and projects built over time.

## Project Structure

```
random-stuff/
├── agent_stuff/
│   ├── AGENTS.md                           # Coding standards for AI-generated code
│   ├── MEMORY_BANK.md                      # Context management for complex projects
│   └── cline_gemini_mcp/                   # BigQuery MCP server management for Cline
├── bq_firebase/                            # Firebase Analytics with BigQuery integration
├── bq_finops_cookbook/                     # BigQuery slot optimization framework
├── bq_geospatial_demo/                     # BigQuery geospatial routing optimization demo
├── bq_kubernetes_comparison/               # BigQuery vs Kubernetes resource management comparison
├── bq_places_insights/                     # BigQuery Places Insights competitive analysis
├── bq_prompt_engineering/                  # BigQuery Data Science Agent example prompts
├── bq_rls_cls_dataform/                    # BigQuery RLS/CLS demo with Dataform
├── bq_scaling_viz/                         # BigQuery scaling visualization
├── dbt_migration_agents/                   # dbt migration toolkit with AI agents
├── dbt_spark_bq/                           # dbt Spark on Dataproc with BigQuery
├── remote_docker/                          # Docker SSH tunnel management
└── samba_management/                       # Samba service management
```

## Projects

### BigQuery Tools

- **bq_firebase**: Jupyter notebook demonstrating Firebase Analytics integration with BigQuery. Shows how to query and analyze Firebase Analytics data exported to BigQuery, including event tracking, user behavior analysis, and conversion funnel analysis.
- **bq_finops_cookbook**: Comprehensive framework for analyzing BigQuery slot utilization and optimizing workload performance. Provides data-driven recommendations for choosing between on-demand, baseline reservations, autoscaling, or hybrid strategies.
- **bq_geospatial_demo**: Delivery route optimization using BigQuery geospatial functions. Includes geohash clustering, nearest neighbor solving, and Maps API integration with both geohash and K-means approaches.
- **bq_kubernetes_comparison**: Visual comparison of BigQuery and Kubernetes workload management strategies.
- **bq_places_insights**: Competitive intelligence framework using BigQuery Places Insights for banking/finance sector. Includes Jakarta banking demo with 7 analytical queries (market landscape, geographic heatmap, quality analysis, white space opportunities, regional performance, operating hours, payment adoption) and comprehensive field reference guide covering 70+ data fields with use cases for market analysis and strategic expansion planning.
- **bq_prompt_engineering**: Example prompts for BigQuery Data Science Agent, categorized by complexity level (simple one-shot to complex multi-step analytical tasks).
- **bq_rls_cls_dataform**: Comprehensive demonstration of BigQuery Row Level Security (RLS) and Column Level Security (CLS) using Dataform with SQL-based data policy approach. Includes both quick SQL demo and production Dataform setup with workflow_settings.yaml configuration.
- **bq_scaling_viz**: Interactive visualization demonstrating BigQuery slot scaling and workload distribution.

### dbt Tools

- **dbt_migration_agents**: AI-assisted dbt migration toolkit with lineage analysis, PRD generation, code refactoring, and validation. Includes sample Bronze/Silver/Gold project with intentional errors for testing migration workflows.
- **dbt_spark_bq**: Jupyter notebook demonstrating dbt Spark on Dataproc with BigQuery integration.

### AI/Agent Tools

- **agent_stuff**: Coding standards based on Google style guides (AGENTS.md), context management guidelines (MEMORY_BANK.md), and Cline MCP server configurations for BigQuery integration.

### Infrastructure

- **remote_docker**: SSH tunnel management for remote Docker daemon access.

## Shell Integration

Add the following aliases to your `.zshrc` or `.bashrc` for quick access to management scripts:

```bash
# Docker SSH Tunnel Management
export DOCKER_HOST=tcp://localhost:2375
alias manage-docker='~/Developer/git/random-stuff/remote_docker/manage_docker_tunnel.sh'

# Cline MCP Management
alias manage-mcp='~/Developer/git/random-stuff/agent_stuff/cline_gemini_mcp/manage_mcp_servers.sh'

# Samba Management
alias manage-samba='~/Developer/git/random-stuff/samba_management/manage_samba.sh'
```

**Usage:**
- `manage-docker`: Start, stop, or check status of Docker SSH tunnel
- `manage-mcp`: Manage Cline MCP server configurations
- `manage-samba`: Manage Samba services (smbd and nmbd) on MacOS

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

## Git Repository Management

### Current Status

This repository is configured with a dual-remote setup:
- main branch → origin/main (GitHub - public content)
- internal-main branch → internal/main (GitLab - Google-internal content)
- internal/ directory excluded from GitHub via .gitignore
- Both branches aligned and up to date with their respective remotes

### Repository Structure

**Local Branches:**
- `main` → pushes to `origin/main` (GitHub - public)
- `internal-main` → pushes to `internal/main` (GitLab - Google-internal)

**Remote Branches:**
- GitHub (`origin`): only has `main` branch
- GitLab (`internal`): only has `main` branch

**Directory Structure:**
- Public content: tracked on both branches
- `internal/` directory: only tracked on `internal-main` branch, excluded from GitHub via `.gitignore`

### Initial Setup (One-Time)

#### 1. Add GitLab Remote

```bash
git remote add internal git@gitlab.com:google-cloud-ce/googlers/USERNAME/REPO.git
```

#### 2. Create and Configure internal-main Branch

```bash
# Create internal-main branch from main
git checkout -b internal-main

# Set up tracking to GitLab's main branch
git branch --set-upstream-to=internal/main internal-main

# Configure push behavior
git config branch.internal-main.push refs/heads/main
git config push.default upstream
```

#### 3. Configure .gitignore

Add to `.gitignore` on main branch:
```
# Internal Google-specific content
internal/
```

This prevents accidental exposure of internal content to GitHub.

#### 4. Add Internal Content

```bash
# On internal-main branch
git checkout internal-main

# Add internal files (force-add since they're in .gitignore)
git add -f internal/

# Commit and push to GitLab
git commit -m "Add internal content"
git push internal internal-main:main
```

### Daily Workflow

#### Working with Public Content (GitHub)

```bash
# Switch to main branch
git checkout main

# Make changes to public files
# ...

# Commit and push to GitHub
git add .
git commit -m "Your commit message"
git push origin main
```

#### Working with Internal Content (GitLab)

```bash
# Switch to internal-main branch
git checkout internal-main

# Make changes to internal/ directory or other files
# ...

# Commit and push to GitLab
git add .
git commit -m "Your commit message"
git push internal  # Automatically pushes to GitLab's main branch
```

#### Syncing Changes Between Branches

When you update public content on main, sync it to internal-main:

```bash
# On internal-main branch
git checkout internal-main

# Merge changes from main
git merge main

# Resolve any conflicts (usually just .gitignore)
# Then push to GitLab
git push internal
```

### Verification

#### Check Branch Configuration

```bash
# View branch tracking
git branch -vv

# Expected output:
# * internal-main [internal/main] ...
#   main          [origin/main] ...
```

#### Check Push Configuration

```bash
# View internal-main configuration
git config --get-regexp "branch.internal-main.*"

# Expected output:
# branch.internal-main.remote internal
# branch.internal-main.merge refs/heads/main
# branch.internal-main.push refs/heads/main
```

#### Test Push (Dry-Run)

```bash
# On internal-main branch
git push --dry-run internal

# Should show: internal-main -> main
# Or: Everything up-to-date
```

### Replication Guide

To set up the same pattern in a new repository:

1. **Create repository on both platforms**
   - GitHub: Create public repository
   - GitLab: Create internal repository

2. **Initialize local repository**
   ```bash
   git init
   git remote add origin git@github.com:USERNAME/REPO.git
   git remote add internal git@gitlab.com:google-cloud-ce/googlers/USERNAME/REPO.git
   ```

3. **Set up main branch**
   ```bash
   # Create initial commit
   git add .
   git commit -m "Initial commit"

   # Push to GitHub
   git push -u origin main
   ```

4. **Set up internal-main branch**
   ```bash
   # Create internal-main from main
   git checkout -b internal-main

   # Configure tracking
   git branch --set-upstream-to=internal/main internal-main
   git config branch.internal-main.push refs/heads/main
   git config push.default upstream

   # Push to GitLab
   git push internal internal-main:main
   ```

5. **Add .gitignore protection**
   ```bash
   # On main branch
   git checkout main
   echo -e "\n# Internal Google-specific content\ninternal/" >> .gitignore
   git add .gitignore
   git commit -m "Add internal/ to gitignore"
   git push origin main

   # Sync to internal-main
   git checkout internal-main
   git merge main
   git push internal
   ```

6. **Add internal content**
   ```bash
   # On internal-main branch
   mkdir -p internal/
   # Add your internal files
   git add -f internal/
   git commit -m "Add internal content"
   git push internal
   ```

### Security Best Practices

1. **Always verify branch before pushing**
   ```bash
   git branch --show-current
   ```

2. **Use dry-run before important pushes**
   ```bash
   git push --dry-run origin  # or internal
   ```

3. **Keep .gitignore in sync**
   - The `internal/` exclusion must exist on main branch
   - Prevents accidental commits to GitHub

4. **Regular audits**
   ```bash
   # Check what's tracked on main
   git ls-tree -r main --name-only | grep "^internal/"
   # Should return nothing

   # Check what's tracked on internal-main
   git ls-tree -r internal-main --name-only | grep "^internal/"
   # Should show internal files
   ```

### Troubleshooting

**Problem: Pushed internal content to GitHub accidentally**

Prevention is key - the `.gitignore` should prevent this. If it happens:
1. Remove the content from GitHub immediately
2. Force push to remove from history if needed
3. Verify `.gitignore` is properly configured

**Problem: Push goes to wrong remote**

Always specify the remote explicitly:
```bash
git push origin main        # For GitHub
git push internal          # For GitLab (from internal-main)
```

**Problem: Branch tracking is incorrect**

Reset the tracking:
```bash
git branch --set-upstream-to=internal/main internal-main
git config branch.internal-main.push refs/heads/main
```
