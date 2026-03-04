# DBT Migration Agent — Enhancement Analysis

> Based on analysis of https://github.com/shanraisshan/claude-code-best-practice
> Generated: Mar 4, 2026
> Status: Baseline analysis for future enhancement

---

## Executive Summary

The `shanraisshan/claude-code-best-practice` repo provides a battle-tested architecture for agent-driven software development. Its core patterns are **directly applicable to our dbt migration agent** without requiring a migration from OpenCode back to Claude Code.

**Key takeaway:** The repo's value is not in the tool choice (Claude Code vs OpenCode), but in the **orchestration patterns** (sub-agent specialization, skill preloading, agent memory, command-driven workflows).

---

## Repo Overview

**Location:** https://github.com/shanraisshan/claude-code-best-practice

**What it is:** A continuously-updated compendium of best practices for building agentic systems in Claude Code. Updated Feb–Mar 2026. Covers:
- Commands (entry points for workflows)
- Sub-agents (specialized agents with restricted tooling)
- Skills (reusable workflows, preloadable or on-demand)
- Agent memory (persistent knowledge per agent)
- MCP servers (external integrations)
- Orchestration workflows (Command → Agent → Skill chains)

**Author:** Shayan Rais (@shanraisshan)

**License:** Open-source (GitHub)

---

## Architecture Patterns Worth Adopting

### Pattern 1: Orchestration Workflow (Command → Agent → Skill)

**Their Example (Weather System):**
```
User → /weather-orchestrator (Command, haiku)
      ↓
      Asks user for unit preference
      ↓
      Spawns weather-agent (Agent, sonnet)
      ├─ Preloaded with: weather-fetcher skill
      ├─ Tools: Read, WebFetch
      └─ Returns: temperature + unit
      ↓
      Spawns weather-svg-creator (Skill)
      ├─ Creates SVG card
      └─ Writes output.md
```

**How it applies to DBT migration:**

Current state (monolithic):
```
opencode /dbt-migrate <task>
  ├─ Analyzes dbt
  ├─ Migrates code
  ├─ Validates
  └─ All in one agent
```

Proposed (orchestrated):
```
/dbt-migrate <project> (Command, haiku)
  ├─ User interaction
  ├─ Spawns dbt-analyzer-agent (Agent, sonnet)
  │  └─ Read-only: understand existing dbt, dependencies
  │
  ├─ Spawns dbt-migrator-agent (Agent, sonnet)
  │  ├─ Preloaded with: dbt-migration-patterns skill
  │  └─ Write/Edit: perform actual migration
  │
  └─ Spawns dbt-validator-agent (Agent, haiku)
     └─ Test: validate migrations, run dbt tests
```

**Why:** Each agent has exactly the tools it needs. Analyzer can't break code. Migrator focuses on transformation. Validator ensures safety. Faster feedback loops.

---

### Pattern 2: Agent Skills (Preloaded Domain Knowledge)

**Their Example:**
```yaml
# .claude/agents/weather-agent.md
name: weather-agent
skills:
  - weather-fetcher  # Injected at startup, full content
tools: Read, WebFetch
model: sonnet
```

**How it applies to DBT migration:**

Create `dbt-migration-patterns` skill with:
```
.claude/skills/dbt-migration-patterns/SKILL.md
  ├─ Common dbt naming conventions (stg_, mart_, int_)
  ├─ Model refactoring patterns
  ├─ Incremental model strategies
  ├─ Source vs ref best practices
  ├─ Your team's dbt.yml structure
  └─ Macro extraction patterns
```

Preload into migrator agent:
```yaml
# .claude/agents/dbt-migrator.md
skills:
  - dbt-migration-patterns
  - dbt-test-best-practices
```

**Why:** Agent starts with institutional knowledge instead of asking "what patterns do you follow?" every time.

---

### Pattern 3: Agent-Specific Persistent Memory

**Their Example:**
```yaml
# .claude/agents/code-reviewer.md
name: code-reviewer
memory: project  # Persistent across runs
```

Stores learnings in `.claude/agent-memory/code-reviewer/MEMORY.md`

**How it applies to DBT migration:**

```yaml
# .claude/agents/dbt-migrator.md
name: dbt-migrator
memory: project  # Stored in .claude/agent-memory/dbt-migrator/
```

The agent maintains:
```
.claude/agent-memory/dbt-migrator/
├── MEMORY.md  (auto-loaded, first 200 lines)
│   ├─ Edge cases discovered (Jinja parsing, circular deps)
│   ├─ Refactoring decisions made
│   └─ Team conventions
├── jinja-edge-cases.md
├── macro-patterns.md
└── test-strategies.md
```

**Why:** Agent learns across runs. No need to re-explain patterns. Knowledge accumulates in the repo.

---

### Pattern 4: Skill Specialization & On-Demand Invocation

**Their Example:**
```
weather-svg-creator (Skill, invoked on-demand via Skill tool)
  ├─ Creates visual output
  └─ Independent from agents
```

**How it applies to DBT migration:**

Create multiple reusable skills:

```
.claude/skills/dbt-validate-migration/SKILL.md
  ├─ dbt parse validation
  ├─ Orphaned model detection
  ├─ Test coverage checks
  └─ Lineage validation

.claude/skills/dbt-lineage-analyzer/SKILL.md
  ├─ Dependency graph visualization
  ├─ Impact analysis (what breaks if I change X?)
  └─ Circular dependency detection

.claude/skills/dbt-model-documenter/SKILL.md
  ├─ Auto-generate descriptions
  ├─ Test generation templates
  └─ Contract definitions
```

These can be:
- Invoked on-demand: `/dbt-validate-migration`
- Called by orchestrator as final validation step
- Reused across different dbt projects

**Why:** Modular, composable, testable independently.

---

## Proposed File Structure

```
your-dbt-repo/
├── .claude/
│   ├── commands/
│   │   └── dbt-migrate.md                    # Entry point (haiku)
│   │       ├─ Asks user: scope, strategy
│   │       ├─ Spawns dbt-analyzer
│   │       ├─ Spawns dbt-migrator
│   │       └─ Spawns dbt-validator
│   │
│   ├── agents/
│   │   ├── dbt-analyzer.md                   # Sonnet, read-only
│   │   │   ├─ Tools: Read, WebFetch, Bash
│   │   │   └─ Scope: understand & report
│   │   │
│   │   ├── dbt-migrator.md                   # Sonnet, write-heavy
│   │   │   ├─ Tools: Read, Write, Edit, Bash
│   │   │   ├─ Skills: dbt-migration-patterns, dbt-test-best-practices
│   │   │   ├─ Memory: project
│   │   │   └─ Scope: perform actual migration
│   │   │
│   │   └── dbt-validator.md                  # Haiku, test-focused
│   │       ├─ Tools: Read, Bash
│   │       ├─ Skills: dbt-validate-migration
│   │       └─ Scope: validation & testing
│   │
│   ├── skills/
│   │   ├── dbt-migration-patterns/
│   │   │   └── SKILL.md
│   │   │       ├─ Naming conventions
│   │   │       ├─ Refactoring patterns
│   │   │       ├─ Model strategies
│   │   │       └─ Your team conventions
│   │   │
│   │   ├── dbt-test-best-practices/
│   │   │   └── SKILL.md
│   │   │       ├─ Generic tests to add
│   │   │       ├─ Coverage expectations
│   │   │       └─ Contract definitions
│   │   │
│   │   ├── dbt-validate-migration/
│   │   │   └── SKILL.md
│   │   │       ├─ dbt parse validation
│   │   │       ├─ Orphaned model detection
│   │   │       ├─ Test coverage checks
│   │   │       └─ Lineage validation
│   │   │
│   │   ├── dbt-lineage-analyzer/
│   │   │   └── SKILL.md
│   │   │       ├─ Dependency visualization
│   │   │       ├─ Impact analysis
│   │   │       └─ Circular dep detection
│   │   │
│   │   └── dbt-model-documenter/
│   │       └── SKILL.md
│   │           ├─ Auto-generate descriptions
│   │           ├─ Test generation
│   │           └─ Contract definitions
│   │
│   ├── agent-memory/
│   │   └── dbt-migrator/
│   │       ├── MEMORY.md                     # First 200 lines auto-loaded
│   │       ├── jinja-edge-cases.md
│   │       ├── macro-patterns.md
│   │       ├── test-strategies.md
│   │       └── team-conventions.md
│   │
│   └── settings.json                         # Global config
│
├── dbt/
│   ├── models/
│   ├── macros/
│   ├── tests/
│   └── dbt_project.yml
│
└── .dbt-migration-logs/                      # Output logs per run
    └── <timestamp>-migration.log
```

---

## Implementation Roadmap

### Phase 1: Quick Wins (Week 1)

1. **Create dbt-migrator agent with memory**
   - Add `memory: project` field
   - Start learning patterns

2. **Extract dbt-migration-patterns skill**
   - Document naming conventions
   - Document refactoring patterns
   - Document model strategies

3. **Preload skill into migrator agent**
   - `skills: [dbt-migration-patterns]`

**Expected outcome:** Agent retains knowledge across runs. No need to re-explain conventions.

### Phase 2: Specialization (Week 2-3)

1. **Create dbt-analyzer agent**
   - Read-only tooling
   - Tasks: understand existing dbt, map dependencies

2. **Create dbt-validator agent**
   - Test-focused tooling
   - Tasks: validate migrations, run tests

3. **Extract validation as independent skill**
   - `dbt-validate-migration`
   - Reusable across projects

**Expected outcome:** Each agent has focused scope. Faster feedback loops. Reusable validation.

### Phase 3: Orchestration (Week 3-4)

1. **Create dbt-migrate command**
   - Entry point
   - Coordinates analyzer → migrator → validator

2. **Refine orchestration workflow**
   - User selects scope (single model, package, entire project)
   - Analyzer reports risks
   - Migrator asks for approval before changes
   - Validator runs final checks

3. **Add logging & checkpointing**
   - Per-run migration logs
   - Ability to retry/resume

**Expected outcome:** Full orchestrated workflow. User controls all decision points.

---

## Key Insights from the Repo

### 1. Skill Preloading > Repeated Prompting

Instead of:
```
"Please follow these conventions: stg_ prefix, use refs, etc."
// Every single migration
```

Do:
```yaml
skills:
  - dbt-migration-patterns  # Loaded once, always available
```

**Impact:** Cleaner prompts, faster execution, consistent patterns.

### 2. Agent Memory = Institutional Learning

Agent maintains its own knowledge base:
- Edge cases it discovered
- Patterns that worked/didn't work
- Team conventions & decisions

**Impact:** Agent gets smarter over time. No need for "refresh my memory" prompts.

### 3. Sub-agent Specialization = Safety

Don't give migrator agent a "delete" tool it doesn't need.
Don't give validator agent a "write" tool it doesn't need.

**Impact:** Safer execution. Clearer intent. Easier debugging.

### 4. Orchestration Workflow = User Control

Command acts as decision point:
- User provides context
- Analyzer makes recommendations
- Migrator asks for approval
- Validator confirms success

**Impact:** Humans stay in the loop. Less chance of surprises.

---

## What NOT to Copy

1. **MCP Server choices** — Their DeepWiki, Playwright choices are demo-specific, not dbt-relevant
2. **Hooks pattern** — Probably overkill for migration unless you need event-driven execution
3. **Status line customization** — Nice-to-have, skip it initially
4. **Excessive documentation** — Their repo is exhaustive by design; extract only what you need

---

## Open Questions for Later

1. **How often should agent memory be curated?**
   - Should it be auto-archived into topic files?
   - Who decides what's worth keeping?

2. **How do we version agent learnings?**
   - Should agent memory be git-committed?
   - Should we track when patterns changed?

3. **Multi-project pattern sharing**
   - Can analyzer/migrator agents work across different dbt projects?
   - Should we have a shared `user` scope memory across projects?

4. **Performance & scale**
   - How does this work on very large dbt projects (1000+ models)?
   - Does skill preloading get expensive?

---

## Reference Links

- **Orchestration Workflow:** https://github.com/shanraisshan/claude-code-best-practice/blob/main/orchestration-workflow/orchestration-workflow.md
- **Skills Best Practice:** https://github.com/shanraisshan/claude-code-best-practice/blob/main/best-practice/claude-skills.md
- **Sub-agents Best Practice:** https://github.com/shanraisshan/claude-code-best-practice/blob/main/best-practice/claude-subagents.md
- **Agent Memory:** https://github.com/shanraisshan/claude-code-best-practice/blob/main/reports/claude-agent-memory.md
- **Full Repo:** https://github.com/shanraisshan/claude-code-best-practice

---

## Next Steps

1. **Read the reference links** above (in order listed)
2. **Identify which patterns fit your OpenCode setup**
3. **Create Phase 1 implementation plan** (Week 1 quick wins)
4. **Start with agent memory** (lowest friction, highest value)
5. **Extract skills incrementally** (as patterns stabilize)
6. **Orchestration comes last** (once agents are stable)

---

**Document Status:** Baseline analysis complete. Ready for detailed enhancement work.

**Updated:** Mar 4, 2026, 15:53 SGT
