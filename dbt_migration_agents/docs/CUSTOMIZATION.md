# Customization Guide

How to extend and customize DBT Migration Agents for your specific needs.

## Overview

The migration framework is designed to be customizable at multiple levels:

1. **Configuration** - Change project names, paths, thresholds
2. **Agent Behavior** - Modify how agents process and respond
3. **Cookbooks** - Change methodology and templates
4. **Validation** - Add custom test patterns
5. **Python Scripts** - Extend lineage analysis

## Configuration Customization

### Adding Custom Config Values

Edit `config/migration_config.yaml`:

```yaml
# Add custom sections
custom:
  company_name: "Acme Corp"
  default_partition_granularity: "day"
  notification_email: "data-team@acme.com"
```

Access in Python:

```python
from config.config_loader import load_config, get_config_value

config = load_config()
company = get_config_value(config, "custom.company_name")
```

Reference in agents by reading the config file.

### Multiple Environments

Create environment-specific configs:

```
config/
├── migration_config.yaml          # Default
├── migration_config.dev.yaml      # Development
├── migration_config.prod.yaml     # Production
```

Use with `-c` flag:

```bash
python lineage_analyzer/dbt_based/analyze_dbt_lineage.py model_name \
  -c config/migration_config.prod.yaml
```

## Agent Customization

### Modifying Agent Behavior

Agent definitions are in `.claude/agents/`. Each file contains:

1. **Frontmatter** - Name, description, tools, model
2. **Instructions** - How the agent should behave
3. **Examples** - Sample inputs and outputs

### Adding a New Agent

1. Create the agent file:

```bash
touch .claude/agents/my_custom_agent.md
```

2. Add frontmatter:

```markdown
---
name: my_custom_agent
description: Description of what this agent does.
tools: Read, Write, Bash
model: sonnet
---
```

3. Add instructions following the pattern of existing agents.

### Customizing Prompts

To change how an agent processes input, edit the "Process" section:

```markdown
## Process

### Step 1: [Your Custom Step]

[Detailed instructions for what the agent should do]

### Step 2: [Another Step]

[More instructions]
```

### Changing Output Format

Modify the "Output" section to change file names or formats:

```markdown
## Output

**File**: `my_custom_outputs/{model_name}_custom_report.md`

**Format**: Markdown with specific sections...
```

## Cookbook Customization

### Modifying the Migration Template

Edit `code_refactor/DBT_MIGRATION_COOKBOOK_TEMPLATE.md`:

1. **Add company-specific steps**:

```markdown
### Step 2.5: Company Compliance Check

Before proceeding, verify:
- [ ] Data classification tags applied
- [ ] Security review completed
- [ ] Documentation updated in wiki
```

2. **Change SQL patterns** (for gold layer models):

```sql
{{ config(
    materialized='incremental',  -- Changed from 'table'
    unique_key='id',
    tags=['gold', 'curated'],
    ...
) }}
```

3. **Add custom validation steps**:

```markdown
### Step 2.3.5: Custom Business Validation

Run company-specific validation:
- Check against reference data
- Verify business rules
- Validate with domain experts
```

### Adding Validation Test Patterns

Edit `migration_validator/VALIDATION_COOKBOOK.md`:

```markdown
### Custom Test: Business Rule Validation

**Purpose**: Verify specific business rules are preserved

**SQL Pattern**:
```sql
SELECT COUNT(*) AS violations
FROM `{table}`
WHERE business_rule_column IS NULL
  AND required_condition = true
```

**Threshold**: 0 violations expected
**Priority**: CRITICAL
```

## Python Script Customization

### Extending Lineage Analysis

Modify `lineage_analyzer/dbt_based/analyze_dbt_lineage.py`:

```python
def custom_analysis(lineage: Dict) -> Dict:
    """Add custom analysis to lineage data.

    Args:
        lineage: Base lineage dictionary.

    Returns:
        Enhanced lineage with custom fields.
    """
    # Add custom analysis
    lineage["custom_metric"] = calculate_custom_metric(lineage)
    return lineage
```

### Adding Custom Validation Tests

Create new test functions in validation scripts:

```python
def test_custom_business_rule():
    """Test custom business rule."""
    query = """
    SELECT COUNT(*) as violations
    FROM `{table}`
    WHERE custom_field NOT IN ('A', 'B', 'C')
    """
    result = run_query(query.format(table=OPTIMIZED_TABLE))
    violations = list(result)[0].violations

    return {
        "test": "Custom Business Rule",
        "priority": "CRITICAL",
        "violations": violations,
        "passed": violations == 0
    }
```

## Adding New Commands

### Creating a Slash Command

1. Create command file:

```bash
touch .claude/commands/my-command.md
```

2. Add content:

```markdown
---
description: My custom command
argument-hint: <arg1> <arg2>
model: sonnet
---

# /my-command

Description of what this command does.

## Usage

```bash
/my-command <arg1> <arg2>
```

## Workflow

### Step 1: [First Step]

[Instructions]

### Step 2: [Second Step]

[Instructions]
```

### Extending the Orchestrator

Add steps to `/migrate-cookbook-generator`:

```markdown
### Step 2.5: Custom Pre-PRD Validation

Before generating PRD, validate:

```
Run custom validation checks:
- Business rule compliance
- Data quality metrics
- Performance projections
```
```

## Integration Points

### Adding Pre/Post Hooks

Create hook scripts that run before or after agents:

```python
# hooks/pre_migration.py
def pre_migration_check(model_name: str, config: dict) -> bool:
    """Run before migration starts."""
    # Check prerequisites
    # Validate permissions
    # Send notifications
    return True

# hooks/post_migration.py
def post_migration_report(model_name: str, results: dict) -> None:
    """Run after migration completes."""
    # Generate summary report
    # Send notifications
    # Update tracking system
```

### External System Integration

Add integration with external systems:

```yaml
# config/migration_config.yaml
integrations:
  slack:
    webhook_url: "https://hooks.slack.com/..."
    channel: "#data-migrations"

  jira:
    base_url: "https://company.atlassian.net"
    project_key: "DATA"

  datadog:
    api_key: "${DATADOG_API_KEY}"
```

## Best Practices

### When Customizing

1. **Version Control** - Track all customizations in git
2. **Document Changes** - Add comments explaining why
3. **Test Thoroughly** - Run on sample data first
4. **Keep Core Intact** - Extend rather than replace
5. **Update Examples** - Keep examples current

### Naming Conventions

- Agent files: `lowercase_with_underscores.md`
- Commands: `kebab-case.md`
- Config keys: `snake_case`
- Python functions: `snake_case`
- Classes: `PascalCase`

### Maintaining Upgrades

To receive updates while keeping customizations:

1. Keep customizations in separate files when possible
2. Document all changes to core files
3. Use git branches for customizations
4. Merge updates carefully

## Examples

### Example: Adding Company Branding

1. Update config:

```yaml
custom:
  company_name: "Acme Data Team"
  prd_footer: "Internal Use Only"
```

2. Modify PRD generator to include:

```markdown
## Footer

{config.custom.prd_footer}
Generated by {config.custom.company_name}
```

### Example: Custom Validation Threshold

1. Add to config:

```yaml
validation:
  custom_thresholds:
    revenue_variance: 0.0001  # 0.01% for revenue
    user_count_variance: 0.01  # 1% for user counts
```

2. Use in validation script:

```python
thresholds = config.get("validation", {}).get("custom_thresholds", {})
revenue_threshold = thresholds.get("revenue_variance", 0.001)
```

## Support

For questions about customization:

1. Check existing agent files for patterns
2. Review the cookbooks for methodology
3. Consult the config example file
4. Open an issue on GitHub
