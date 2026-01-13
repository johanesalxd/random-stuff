---
description: Orchestrates generation of PRD and migration cookbook for DBT gold layer migration
argument-hint: <model_file_path> <target_project.dataset>
model: sonnet
---

# /migrate-cookbook-generator

Orchestrates the generation of a PRD and migration cookbook for DBT model gold layer migration.

## Configuration

**CRITICAL**: Before running this command, ensure `config/migration_config.yaml` is configured for your project.

The orchestrator reads configuration from `config/migration_config.yaml` to determine:
- GCP project names and billing project
- DBT model paths (staging, marts, gold layer)
- Output directories for artifacts
- Validation thresholds

## Usage

```bash
/migrate-cookbook-generator <model_file_path> <target_project.dataset>
```

**Example**:
```bash
/migrate-cookbook-generator models/marts/reporting/survey/my_model.sql my-project.my_dataset
```

## Description

This command orchestrates a 5-step workflow:

0. **Configuration Loading & Lineage Validation** (Load config, validate/generate lineage)
1. **Analyze Dependencies** (Subagent 0: Lineage Analyzer)
2. **Generate PRD** (Subagent 1: PRD Generator)
3. **Manual Review & Approval** (User checkpoint)
4. **Generate Migration Cookbook** (Subagent 3: Migration Cookbook Generator)

## Workflow

### Step 0: Load Configuration & Validate Lineage

**0.1 Load Configuration**

First, read and validate the configuration file:

```
Read config/migration_config.yaml

Validate required settings:
- gcp.billing_project is set
- gcp.projects.bronze is set
- gcp.projects.silver is set
- gcp.projects.gold is set
- dbt.silver_models path exists
- dbt.gold_models path is defined
```

**If config is missing or invalid:**
```
Configuration Error: [specific error message]

Please ensure config/migration_config.yaml exists and contains valid settings.
Copy from config/migration_config.example.yaml if needed.
```

**0.2 Extract Model Name**

Extract model name from file path:
- Input: `models/marts/reporting/resolve/resolve_break_down_with_jobs.sql`
- Extract: `resolve_break_down_with_jobs`

**0.3 Check Lineage Files**

Check if DBT lineage file exists and contains the model:
```
File: lineage_analyzer/outputs/lineage_dbt_{model_name}.md
Action: Search for model name in file content
```

**Validation Scenarios:**

**Scenario A: DBT Lineage Available**
```
✅ DBT lineage: Found model in lineage_dbt_{model_name}.md

Using DBT lineage for analysis.

Proceeding to Step 1: Analyze Dependencies...
```

**Scenario B: DBT Lineage Missing/Not Relevant**
```
⚠️ DBT lineage: File does not exist or does not contain '{model_name}'

Generating DBT lineage for this model...

[Invoke dbt_lineage_generator subagent]

✅ DBT lineage generated: lineage_dbt_{model_name}.md

Proceeding to Step 1: Analyze Dependencies...
```

**Invoke DBT Lineage Generator (when needed):**

```
Invoke dbt_lineage_generator subagent:
- Model name: {extracted_model_name}
- Config path: config/migration_config.yaml
- Expected output: lineage_analyzer/outputs/lineage_dbt_{model_name}.md
```

**If generation fails:**
- Display error message from subagent
- Ask user to verify model exists: `dbt ls --select {model_name}`
- Ask user to regenerate manifest if needed: `dbt parse`
- STOP and wait for user to resolve issue

### Step 1: Analyze Dependencies

Invoke Subagent 0 (Lineage Analyzer) with the provided model file path:

```
Analyze dependencies for <model_file_path>
Using config: config/migration_config.yaml
```

**Subagent 0 will**:
- Read the target DBT model file
- Read configuration for project names and paths
- Study DBT lineage documentation
- Create complete dependency inventory
- Analyze business logic in each staging model SQL file
- Classify complexity (LOW/MEDIUM/HIGH)
- Determine migration priorities (Priority 1-4)
- Generate comprehensive migration analysis document

**Output**: `{config.outputs.prd}/{model_name}_migration_analysis.md`

**Present analysis summary to user** (informational, not requiring approval):
```
Migration Analysis Generated: prd_generator/outputs/{model_name}_migration_analysis.md

Analysis Summary:
- Total Dependencies: X (Y staging, Z marts, W seeds)
- Migration Scope: N models recommended for gold layer
- Priorities:
  * Priority 1 (Simple - LOW): X models
  * Priority 2 (Moderate - MEDIUM): Y models
  * Priority 3 (Complex - HIGH): Z models
  * Priority 4 (Future): W models

Proceeding to PRD generation...
```

### Step 2: Generate PRD

Invoke Subagent 1 (PRD Generator) with the migration analysis and target parameters:

```
Generate PRD from migration analysis:
@prd_generator/outputs/{model_name}_migration_analysis.md
targeting <target_project.dataset>
Using config: config/migration_config.yaml
```

**Parse target_project.dataset**:
- Extract project: Split on '.' to get first part (e.g., `my-gcp-project`)
- Extract dataset: Split on '.' to get second part (e.g., `my_dataset`)

**Subagent 1 will**:
- Read the migration analysis document from Subagent 0
- Read configuration for project names and architecture description
- Extract model recommendations with priorities and complexity classifications
- Parse business logic details for each model
- Read original staging model SQL files for BEFORE examples
- Generate comprehensive PRD using target project/dataset parameters
- Create complete SQL BEFORE/AFTER for each model

**Output**: `{config.outputs.prd}/{model_name}_dbt_refactoring_prd.md`

**Present to user**:
```
PRD Generated: prd_generator/outputs/{model_name}_dbt_refactoring_prd.md

Executive Summary:
- Total Dependencies: X
- Migration Scope: N models
- Target: {target_project}.{target_dataset} gold layer
- Source: {config.gcp.projects.bronze} bronze layer

Please review the PRD document:
@prd_generator/outputs/{model_name}_dbt_refactoring_prd.md

Key sections to review:
- Executive Summary (objectives, business impact)
- Models to Migrate Table (all models with business logic)
- Technical Requirements (complete SQL BEFORE/AFTER for each model)
- Validation Tests
- Implementation Steps

Once reviewed, please respond with:
- "Approved" to proceed with cookbook generation
- "Rejected" with feedback for revisions
```

### Step 3: Manual Review Checkpoint

**CRITICAL**: Wait for explicit user approval before proceeding.

**User responses**:
- **"Approved"** or **"Approved, proceed with cookbook generation"** → Proceed to Step 4
- **"Rejected"** or feedback → Stop and inform user to provide corrections

**If user approves**: Proceed to Step 4

**If user rejects**:
```
PRD requires revisions. Please provide feedback on what needs to be changed.

You can:
1. Manually edit the PRD: @prd_generator/outputs/{model_name}_dbt_refactoring_prd.md
2. Re-run this command after making changes
3. Provide specific corrections now for me to apply
```

### Step 4: Generate Migration Cookbook

After user approval, invoke Subagent 3 (Migration Cookbook Generator):

```
Generate migration cookbook from approved PRD:
@prd_generator/outputs/{model_name}_dbt_refactoring_prd.md
targeting <target_project.dataset>
Using config: config/migration_config.yaml
```

**Subagent 3 will**:
- Read the approved PRD
- Read configuration for all project/path values
- Extract all models, business logic, source mappings, priorities
- Customize `code_refactor/DBT_MIGRATION_COOKBOOK_TEMPLATE.md`
- Replace all placeholders with PRD data and config values
- Generate complete migration cookbook

**Output**: `{config.outputs.cookbooks}/gold_{model_name}_cookbook.md`

**Present to user**:
```
Migration Cookbook Generated: code_refactor/outputs/gold_{model_name}_cookbook.md

Cookbook Details:
- Migration Scope: N models
- Target Project: {target_project}
- Target Dataset: {target_dataset}
- Source Project: {config.gcp.projects.bronze}

Ready for Execution.

Next Step:
To start the migration, execute:

"Execute migration following @code_refactor/outputs/gold_{model_name}_cookbook.md"

This will start the sequential migration process where I will:
- Create directory structure
- Migrate models ONE AT A TIME
- Validate each model using the validation_subagent
- Apply SQL refinement if validation fails
- Document all results
- Wait for your confirmation before each model migration
```

## Parameters

- **model_file_path** (required): Path to the DBT model file to migrate
  - Example: `models/marts/reporting/survey/my_model.sql`
  - Must be a valid path to a `.sql` file in the models directory

- **target_project.dataset** (required): Target GCP project and dataset for gold layer models
  - Format: `project.dataset`
  - Example: `my-gcp-project.my_dataset`
  - Project: GCP project ID where gold models will be created
  - Dataset: BigQuery dataset/schema within the target project

## Outputs

1. **Migration Analysis**: `prd_generator/outputs/{model_name}_migration_analysis.md`
2. **PRD Document**: `prd_generator/outputs/{model_name}_dbt_refactoring_prd.md`
3. **Migration Cookbook**: `code_refactor/outputs/gold_{model_name}_cookbook.md` (after approval)

## Sub-Agents Invoked

1. **dbt_lineage_generator**: `.claude/agents/dbt_lineage_generator.md` (invoked conditionally in Step 0)
2. **Subagent 0**: `.claude/agents/lineage_analyzer.md` (Lineage Analyzer)
3. **Subagent 1**: `.claude/agents/prd_generator.md` (PRD Generator)
4. **Subagent 3**: `.claude/agents/migration_cookbook_generator.md` (Migration Cookbook Generator)

**Note**: Subagent 2 (validation_subagent.md) is NOT invoked by this command - it's invoked later during cookbook execution.

## User Control Points

1. **PRD Review & Approval**: User must explicitly approve PRD before cookbook generation
2. **Cookbook Execution**: User chooses when to execute the cookbook (not automatic)

## Example Session

```
User: /migrate-cookbook-generator models/marts/reporting/survey/my_model.sql my-project.my_dataset

Claude: [Step 0: Load Configuration & Validate Lineage]

Claude: Loading configuration from config/migration_config.yaml...
✅ Configuration valid

Validating existing lineage files...
✅ DBT lineage: Found model in lineage_dbt_my_model.md

Proceeding to Step 1: Analyze Dependencies...

Claude: [Invokes Subagent 0: Lineage Analyzer]

Claude: Migration Analysis Generated: prd_generator/outputs/my_model_migration_analysis.md

Analysis Summary:
- Total Dependencies: 15 (10 staging, 4 marts, 1 seed)
- Migration Scope: 8 models recommended for gold layer
...

Proceeding to PRD generation...

Claude: [Invokes Subagent 1: PRD Generator]

Claude: PRD Generated: prd_generator/outputs/my_model_dbt_refactoring_prd.md
...

Please review: @prd_generator/outputs/my_model_dbt_refactoring_prd.md

Respond with "Approved" to proceed with cookbook generation.

User: Approved

Claude: [Invokes Subagent 3: Migration Cookbook Generator]

Claude: Migration Cookbook Generated: code_refactor/outputs/gold_my_model_cookbook.md
...

Ready for execution.

Next Step:
"Execute migration following @code_refactor/outputs/gold_my_model_cookbook.md"
```

## Important Notes

1. **Configuration Required**: This command requires `config/migration_config.yaml` to be configured
2. **Manual Checkpoints**: Includes a mandatory manual review checkpoint for PRD approval
3. **No Automatic Execution**: The cookbook is generated but NOT automatically executed
4. **User Confirmation Required**: User must explicitly request cookbook execution
5. **Validation Later**: The validation_subagent is invoked during cookbook execution, not by this command

---

**Command Type**: Orchestrator
**Configuration**: config/migration_config.yaml
**Sub-Agents**: dbt_lineage_generator, lineage_analyzer, prd_generator, migration_cookbook_generator
**Manual Checkpoints**: PRD approval
**Outputs**: Migration analysis, PRD document, Migration cookbook
