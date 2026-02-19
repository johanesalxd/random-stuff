# OpenClaw + Anthropic: Workspace & Prompt Architecture Guide

> Practical patterns for running OpenClaw with Anthropic Claude models (Claude Max plan).
> Evolved from `openclaw-gemini-guide.md` — architectural patterns are preserved,
> Gemini-specific content replaced with Anthropic equivalents.
>
> **OpenClaw docs:** https://docs.openclaw.ai/
> **Last updated:** 2026-02-19

---

## 1. Workspace Architecture

### Standard Files (auto-injected every turn)

OpenClaw injects these files into the system prompt automatically on every
agent turn. Do NOT duplicate their content in cron job payloads.

| File | Purpose | Sub-agent visible? |
|------|---------|-------------------|
| `AGENTS.md` | Operating instructions, boot sequence, protocols, rules | Yes |
| `SOUL.md` | Persona, tone, boundaries, journaling protocol | No |
| `IDENTITY.md` | Name, creature, vibe, role, channels, emoji | No |
| `USER.md` | User profile (name, preferences, interests) | No |
| `TOOLS.md` | Infrastructure notes, entity IDs, paths, device references | Yes |
| `HEARTBEAT.md` | Periodic health check checklist | No |
| `MEMORY.md` | Curated long-term memory (decisions, preferences, lessons) | No |

**Key distinction:** Sub-agents and isolated cron agents only receive
`AGENTS.md` + `TOOLS.md`. This is why cron payloads must be self-contained
— the agent cannot rely on persona, user profile, or memory files.

### Non-Standard Files (loaded via boot sequence)

These files are NOT auto-injected. The boot sequence in `AGENTS.md` must
explicitly instruct the agent to read them at session start.

| File | Purpose | Memory Tier |
|------|---------|-------------|
| `short-term-memory.md` | Transactional task state tracking | L1 (STM) |
| `memory/projects.md` | Project context, active state | L2 (Projects) |

### On-Demand Files (searched, not loaded at boot)

| Path | Purpose | Access Method | Memory Tier |
|------|---------|---------------|-------------|
| `memory/YYYY-MM-DD.md` (recent) | Daily session logs | Boot step (explicit read) | L3 |
| `memory/*.md` (older) | Historical journal archive | `memory_search` | L3 |

### Content Taxonomy

| Content Type | Belongs In | NOT In |
|---|---|---|
| Operational protocols, rules, boot sequence | `AGENTS.md` | ~~MEMORY.md~~ |
| Curated facts, decisions, lessons learned | `MEMORY.md` | ~~AGENTS.md~~ |
| Persona, tone, vibe, journaling protocol | `SOUL.md` | |
| Identity card (name, creature, emoji) | `IDENTITY.md` | |
| User profile | `USER.md` | |
| Infrastructure (IPs, entities, paths) | `TOOLS.md` | |
| Health check protocol | `HEARTBEAT.md` | |
| Active project state | `memory/projects.md` | |
| Transactional task tracking | `short-term-memory.md` | |
| Daily session journals | `memory/YYYY-MM-DD.md` | |

### Memory Tier Architecture

```
L1 (STM)      : short-term-memory.md      -- Active tasks, read at boot
L2 (Projects)  : memory/projects.md        -- Project context, read at boot
L3 (Search)    : memory_search             -- Searches memory/*.md + MEMORY.md
```

---

## 2. Anthropic Model Strategy

### Model Comparison

| Aspect | Haiku | Sonnet | Opus |
|--------|-------|--------|------|
| Latency | Very low (~1-3s) | Low-Medium (~3-8s) | Higher (~8-20s) |
| Cost (Max plan) | Included | Included | Included |
| Instruction-following | Good | Excellent | Excellent |
| Reasoning depth | Adequate for structured tasks | Strong | Deepest |
| Best for | Spoon-fed crons, atomic steps | Conversation, orchestration, synthesis | Complex multi-step analysis |

**Claude Max plan note:** On Claude Max, cost-per-call is not the primary
concern — execution time and quality are. However, haiku is still preferable
for timeout-constrained cron jobs because it's faster, not cheaper.

### Thinking Budget Levels

Claude models support configurable thinking budgets.

| Level | When to Use | Trade-off |
|-------|-------------|-----------|
| Low | Cron jobs, atomic tool calls, spoon-fed prompts | Fastest. Sufficient when the prompt does the thinking for the model. |
| Medium | Interactive conversation, moderate ambiguity | Good balance for reasoning through unclear tasks. |
| High | Complex multi-step analysis, research synthesis | Slowest. Use when the model must reason deeply, not just execute. |

**Rule of thumb:** If the prompt already tells the model exactly what to do
step-by-step, low thinking is sufficient. Save medium/high for tasks where
the model must determine *what* to do, not just *how*.

### Model Assignment Framework

Recommended assignments across OpenClaw contexts:

| Context | Model | Thinking | Rationale |
|---------|-------|----------|-----------|
| Conversation (main) | `claude-sonnet-4-6` | Low | Interactive; balanced reasoning and speed |
| Cron / Automation | `claude-sonnet-4-6` | Low | Spoon-fed prompts handle complexity; revisit haiku |
| Research / Deep analysis | `claude-opus-4-6` | Low | Deep synthesis, multi-step analysis |
| Coding (opencode) | `claude-sonnet-4-6` | Low | Via `opencode run -m anthropic/claude-sonnet-4-6` |

**Cron timeout constraint:** OpenClaw cron jobs have an execution timeout
(observed ~120s in practice). For complex multi-step payloads with slow tools
(e.g., feed scanners, multiple web searches), the bottleneck is tool execution
time — not model latency. Prompt optimisation (fewer steps, smarter tool order)
is a higher-leverage fix than switching models.

**Haiku for crons (backlog):** Haiku is a valid candidate for spoon-fed
cron jobs. The prompts already do all the reasoning — the model just executes.
Evaluate once the prompt architecture is cleaned up in a dedicated session.

### When to Escalate Thinking Level

- **Sonnet + medium/high:** Genuine ambiguity, multi-source conflict resolution,
  orchestration decisions with real stakes (financial, config changes).
- **Opus:** Reserve for truly complex synthesis tasks. Rare, explicit request only.
- **Never escalate for crons:** The prompt structure handles complexity; model
  reasoning budget is wasted on structured execution tasks.

---

## 3. Cron Job Architecture

### Isolated Agent Context

Per OpenClaw docs, isolated cron agents only receive:
- `AGENTS.md` (auto-injected)
- `TOOLS.md` (auto-injected)

They do NOT receive: SOUL.md, IDENTITY.md, USER.md, HEARTBEAT.md, MEMORY.md.
Cron payloads must be **completely self-contained** — the agent has no persona
context, no user preferences, and no memory outside of explicit file reads.

### The Spoon-Feeding Pattern

Cron payloads follow this structure, hardcoding everything the isolated agent needs:

```
[SYSTEM_DIRECTIVE]    -- Behavioral constraints (atomic execution, no hallucination)
[CRITICAL]            -- (Optional) Hard delivery/safety guards (e.g., NO_REPLY guard)
[TOOLS]               -- Which tools to use (exec commands, native tools)
[PHASE 1: BOOT]       -- Explicit file reads (absolute paths)
[PHASE 2: DATA]       -- Numbered atomic steps, one command each
[PHASE 3: SYNTHESIS]  -- Output format, persona, comparison directives
[CORE OBJECTIVE]      -- Single-sentence mission
```

**`[CRITICAL]` (optional).** Hard constraints that prevent system-level
failures. Keep short — one or two lines max. Omit if no delivery/safety concerns.

### Atomic Execution Rules

1. **One command per step.** Each numbered step executes exactly one tool call.
2. **No shell chaining.** Never use `&&`, `;`, or `|` to combine commands.
3. **Absolute paths only.** The agent has no working directory context.
4. **Failure handling.** If a step fails, mark it `[DATA UNAVAILABLE]` and continue.
5. **No SKILL.md reads in payloads.** Hardcode exact CLI commands.
6. **`web_search` is a native tool.** Never wrap it in `exec`. Call it directly.

### Payload Skeleton

```
You are a data collection and reporting agent.

[SYSTEM_DIRECTIVE]
- Execute steps EXACTLY as numbered. Do NOT skip or reorder.
- Do NOT hallucinate data. If a tool call fails, record [DATA UNAVAILABLE].
- Use ONLY the tools listed below.

[CRITICAL]: NEVER include the token 'NO_REPLY' in your output.
Your response MUST be delivered to the user.

[TOOLS]
- `exec`: For running CLI commands
- `web_search`: For internet searches (NATIVE tool, do NOT use exec)
- `read`: For reading workspace files

[PHASE 1: BOOT]
Step 1: Read file at /absolute/path/to/context.md

[PHASE 2: DATA COLLECTION]
Step 2: exec: your-cli-tool subcommand --flag value
Step 3: exec: another-tool query "search terms"
Step 4: web_search: "topic for research"

[PHASE 3: SYNTHESIS]
Combine all collected data into a structured report.
- Section A: Summary of Step 2 results
- Section B: Summary of Step 3 results
- Cross-validate: if a signal appears in both Step 3 and Step 4, flag as [STRONG SIGNAL]

[CORE OBJECTIVE]
Deliver a briefing using ONLY verified data from the steps above.
```

### Common Gotchas (Anthropic-specific)

**Sonnet follows complex instructions better than flash did.** The excessive
guardrails in current cron prompts (repeated directives, heavy [SYSTEM_DIRECTIVE]
blocks) were added to combat gemini-flash laziness. Sonnet/Haiku need less
hand-holding — the prompts can be simplified significantly in the next revision.

**Delivery-suppressing tokens.** Isolated cron agents can hallucinate `NO_REPLY`
at the end of their output. In OpenClaw, `NO_REPLY` suppresses delivery to
Telegram. Always include the prohibition in `[CRITICAL]`.

**Session staleness after major changes.** After significant structural changes
to cron payloads or workspace files, start a new agent session before evaluating
results. Long sessions accumulate stale context.

**Slow tools still dominate runtime.** In complex multi-step crons, execution
time is driven by tool calls (feed scanners can take 30-40s alone, multiple
web searches compound), not model latency. Model switches don't fix timeout
risk — prompt optimisation and step reduction do.

---

## 4. Prompt Architecture Considerations

### The Causal Attention Problem

LLMs process text left-to-right with causal attention. When the model processes
early context (data, tool outputs), it cannot yet "see" instructions that appear
later. This creates the "Lost in the Middle" problem in long prompts.

### Why Atomic Execution Mitigates This

The Spoon-Feeding Pattern is a structural solution. Each step processes one
source independently:

```
[instructions]
[tool_call_1] -> [result_1]    -- small, focused context
[tool_call_2] -> [result_2]    -- small, focused context
...
[synthesize using above]       -- structured tool_call/result pairs in KV cache
```

Context never grows into a monolithic block. By synthesis time, data is
organized as clean `tool_call → tool_result` pairs.

### Instruction Repetition (When It Helps)

The "Instruction Sandwich" (repeating key instructions at top and bottom) is
effective for:
- Single-shot prompts with 10K+ tokens of dense context between instructions and question
- RAG retrieval with many stuffed documents

**Not worth doing** for OpenClaw spoon-fed crons — context is already small and
structured per step. Token overhead adds latency for marginal quality gain.

### Goal-First Priming

State the core objective at the very top of the prompt, before data or tool calls.
The Spoon-Feeding Pattern already does this via `[SYSTEM_DIRECTIVE]`. This ensures
all subsequent content is processed through the lens of the goal.

---

## 5. Coding Architecture

### OpenCode Integration

Coding tasks use `opencode` via the Anthropic provider. Planning is always
orchestrator-level — the agent presents a technical plan, user approves, then
opencode builds.

```bash
# Standard build command
exec pty:true background:true workdir:/path/to/project \
  command:"opencode run -m anthropic/claude-sonnet-4-6 'task description'"
```

**Key rules:**
- Planning stays at orchestrator level — never ask opencode to plan AND build in one shot
- `git init` always. Local commits only. No `git push` without explicit user action
- Local unit/functional tests with mocks. No external deps
- Project root: your preferred git directory (e.g., `~/Developer/git/`)

**opencode config:** `~/.config/opencode/opencode.json`
- Coding standards file can be auto-loaded as an instruction file
- Anthropic provider authenticated via Claude Max plan

---

## 6. Operational Procedures

### Cron Job Creation Checklist

```
[ ] Verify all CLI commands with <tool> --help (not just SKILL.md)
[ ] Use absolute paths for all file reads
[ ] One command per numbered step (atomic execution)
[ ] web_search used as native tool (not via exec)
[ ] Failure handling in SYSTEM_DIRECTIVE ([DATA UNAVAILABLE])
[ ] Total estimated execution time well under ~120s timeout
[ ] NO_REPLY guard in [CRITICAL] block for announce delivery jobs
[ ] Model set appropriately (sonnet or haiku with low thinking)
```

### Verification Checklist (after workspace changes)

```
[ ] AGENTS.md boot steps point to valid files
[ ] AGENTS.md model assignments reflect current active models
[ ] SOUL.md references to AGENTS.md match actual section headers
[ ] SOUL.md Distill & Flush targets exist (MEMORY.md, memory/projects.md)
[ ] MEMORY.md decisions log updated with any architectural changes
[ ] memory/projects.md backlog is current
[ ] Cron job absolute paths match actual file locations
[ ] Cron job model assignments match AGENTS.md model section
[ ] Active skill roster reflects current active/disabled skills
```

### CLI Tool Version Upgrades

When upgrading tools used in cron jobs:
1. Check new version: `<tool> --version`
2. Compare help: `<tool> --help` and `<tool> <subcommand> --help`
3. Test all hardcoded cron commands against the new version
4. Update cron payloads if syntax changed
5. Always treat `--help` as source of truth, not SKILL.md

---

## 7. Reference Links

| Topic | URL |
|-------|-----|
| OpenClaw Docs | https://docs.openclaw.ai/ |
| Agent Workspace | https://docs.openclaw.ai/concepts/agent-workspace |
| System Prompt | https://docs.openclaw.ai/concepts/system-prompt |
| Cron Jobs | https://docs.openclaw.ai/automation/cron-jobs |
| Skills | https://docs.openclaw.ai/tools/skills |

---

## 8. Revision History

| Date | Change |
|------|--------|
| 2026-02-19 | Initial creation. Forked from `openclaw-gemini-guide.md`. Replaced Gemini model strategy with Anthropic. Updated model assignments, coding architecture, and cron notes to reflect Claude Max migration. |
