# OpenClaw + Gemini: Workspace & Prompt Architecture Guide

> Practical patterns for running OpenClaw with Google Gemini models.
> Covers workspace conventions, model strategy, cron architecture, and prompt design.
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
-- the agent cannot rely on persona, user profile, or memory files.

**Relevant doc pages:**
- Agent Workspace: https://docs.openclaw.ai/concepts/agent-workspace
- System Prompt: https://docs.openclaw.ai/concepts/system-prompt
- Context: https://docs.openclaw.ai/concepts/context

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
| `memory/*.md` (older) | Historical journal archive | `memory_search` / search tool | L3 |

### Content Taxonomy

Keep content in the right file. Misplacement causes duplication and drift.

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
L3 (Search)    : memory_search / qmd       -- Searches memory/*.md + MEMORY.md
```

---

## 2. Gemini Model Strategy

### Flash vs Pro

| Aspect | Gemini Flash | Gemini Pro |
|--------|-------------|------------|
| Latency | Low (~1-3s) | Higher (~5-15s) |
| Cost | Significantly cheaper | ~10-20x more expensive |
| Context window | Large (1M tokens) | Large (1M+ tokens) |
| Reasoning depth | Good for structured tasks | Better for complex synthesis |
| Best for | Cron jobs, quick responses, atomic steps | Deep analysis, multi-step reasoning |

**Cost implication:** For cron jobs that run multiple times daily, the cost
difference compounds. Flash is the practical choice for frequent automation.

### Thinking Budget Levels

Gemini models support configurable "thinking" budgets that control how much
internal reasoning the model performs before responding.

| Level | When to Use | Trade-off |
|-------|-------------|-----------|
| Low | Cron jobs, atomic tool calls, spoon-fed prompts | Fastest, cheapest. Sufficient when the prompt does the thinking for the model. |
| Medium | Interactive conversation, moderate complexity | Good balance. The model reasons through ambiguity without excessive latency. |
| High | Complex multi-step analysis, research synthesis | Slowest, most expensive. Use when the task genuinely requires deep reasoning. |

**Rule of thumb:** If the prompt already tells the model exactly what to do
(step-by-step), low thinking is sufficient. The model doesn't need to
"figure out" the plan -- it just executes. Save medium/high for tasks where
the model must reason about what to do, not just how.

### Model Assignment Framework

A recommended pattern for assigning models across different OpenClaw contexts:

| Context | Recommended Model | Thinking | Rationale |
|---------|------------------|----------|-----------|
| Conversation (main) | Flash | Medium | Interactive; needs reasoning but also speed |
| Cron / Automation | Flash | Low | Timeout-constrained; spoon-fed prompts handle complexity |
| Research / Deep analysis | Pro | Medium-High | Worth the cost for synthesis quality |

**Cron timeout constraint:** OpenClaw cron jobs have approximately a 60-second
execution timeout. This rules out Pro models for cron use -- they're too slow.
Flash with low thinking fits comfortably within the window, even for multi-step
payloads.

---

## 3. Cron Job Architecture

### Isolated Agent Context

Per OpenClaw docs, isolated cron agents only receive:
- `AGENTS.md` (auto-injected)
- `TOOLS.md` (auto-injected)

They do NOT receive: SOUL.md, IDENTITY.md, USER.md, HEARTBEAT.md, MEMORY.md.
This means cron payloads must be **completely self-contained** -- the agent
has no persona context, no user preferences, and no memory.

### The Spoon-Feeding Pattern

Cron payloads should follow this structure, hardcoding everything the
isolated agent needs:

```
[SYSTEM_DIRECTIVE]    -- Behavioral constraints (atomic execution, no hallucination)
[CRITICAL]            -- (Optional) Hard delivery/safety guards (e.g., forbidden tokens)
[TOOLS]               -- Which tools to use (exec commands, native tools)
[PHASE 1: BOOT]       -- Explicit file reads (absolute paths)
[PHASE 2: DATA]       -- Numbered atomic steps, one command each
[PHASE 3: SYNTHESIS]  -- Output format, persona, comparison directives
[CORE OBJECTIVE]      -- Single-sentence mission
```

**`[CRITICAL]` (optional).** Hard constraints that prevent system-level
failures. Use this for delivery guards (e.g., forbidden tokens that suppress
output), safety rails, or any constraint where violation breaks the pipeline
-- not just degrades quality. Keep this section short; one or two lines
maximum. If you have no delivery or safety concerns, omit this section
entirely.

### Atomic Execution Rules

1. **One command per step.** Each numbered step executes exactly one tool call.
2. **No shell chaining.** Never use `&&`, `;`, or `|` to combine commands.
3. **Absolute paths only.** The agent has no working directory context.
4. **Failure handling.** If a step fails, mark it `[DATA UNAVAILABLE]` and
   continue to the next step. Never halt the entire payload for one failure.
5. **No SKILL.md reads in payloads.** Hardcode the exact CLI commands instead
   of instructing the agent to read skill documentation at runtime.

### Why Spoon-Feeding Works

This pattern exists because of how Gemini (and LLMs in general) handle
instructions. With low thinking budget, the model executes instructions
literally rather than interpreting them creatively. By providing explicit,
numbered, atomic steps, you:

- Remove ambiguity (the model doesn't need to plan)
- Reduce the chance of hallucinated tool calls
- Keep each step's context small and focused
- Avoid the "Lost in the Middle" attention decay problem (see Section 4)

### Payload Skeleton (Generic Example)

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
- `read_file`: For reading workspace files

[PHASE 1: BOOT]
Step 1: Read file at /absolute/path/to/context.md

[PHASE 2: DATA COLLECTION]
Step 2: exec: your-cli-tool subcommand --flag value
Step 3: exec: another-tool query "search terms"
Step 4: web_search: "topic for general news comparison"

[PHASE 3: SYNTHESIS]
Combine all collected data into a structured report:
- Section A: Summary of Step 2 results
- Section B: Summary of Step 3 results
- Section C: Compare Step 3 signals against Step 4 general news
- Flag any discrepancies between specialized sources and general news

[CORE OBJECTIVE]
Deliver a comprehensive briefing using ONLY verified data from the steps above.
```

### Common Gotchas

**`web_search` is a native OpenClaw tool.** It is NOT a shell binary. Never
wrap it in an `exec` call. Use it directly as a tool call. This is one of the
most common mistakes for new OpenClaw users configuring cron jobs.

**SKILL.md files may be outdated.** OpenClaw bundles SKILL.md documentation
for installed tools, but these files may lag behind the actual CLI version.
Always verify available commands and flags with `<tool> --help` before
hardcoding commands in cron payloads. A command that works according to
SKILL.md might not exist in the installed version, or vice versa.

**Slow tools need timeout awareness.** Some tools (e.g., blog scanners that
check 50+ feeds, or data scrapers) can take 30-40 seconds alone. If your
cron payload has multiple slow tools, you risk hitting the 60-second timeout.
Options:
- Split into separate cron jobs that run at staggered times
- Reduce the scope of slow tools (fewer feeds, narrower queries)
- Use Flash with low thinking to minimize model processing time

**Delivery-suppressing tokens in isolated sessions.** Isolated cron agents
can hallucinate system tokens like `NO_REPLY` at the end of their output.
In OpenClaw, `NO_REPLY` triggers the delivery system to suppress the message,
preventing it from reaching the user's Telegram/channel. Always include an
explicit prohibition in the `[CRITICAL]` block:

```
[CRITICAL]: NEVER include the token 'NO_REPLY' in your output.
Your response MUST be delivered to the user.
```

This is especially important for `announce` delivery mode where silent
suppression means the report is generated but never delivered.

**Session staleness after major changes.** After making significant
structural changes to cron payloads or workspace files, start a new agent
session before evaluating results or making further adjustments. Long
sessions accumulate stale context -- the agent may reason against outdated
prompt versions, suggest fixes for already-resolved issues, or recommend
patterns that contradict changes made earlier in the same session. This
is particularly dangerous when the agent suggests "fixes" based on the
pre-edit state of a prompt it helped rewrite.

---

## 4. Prompt Architecture Considerations

### The Causal Attention Problem

LLMs process text left-to-right with causal attention. When the model
processes early context (data, tool outputs), it cannot yet "see" the
instructions that appear later in the prompt. The internal representation
of early tokens is formed without knowledge of the final question or
synthesis rules.

This creates a real problem in long prompts:

```
[instructions] [10K+ tokens of raw data] [question/synthesis rules]
```

The model's attention on the early data is not focused through the lens of
the final question. This is sometimes called "Lost in the Middle" -- the
model attends well to the beginning and end of context, but less to the
middle.

### Why Atomic Execution Already Mitigates This

The Spoon-Feeding Pattern (Section 3) is a structural solution to this
problem. Instead of dumping all data into one massive prompt, each step
processes one source independently:

```
[instructions]
[tool_call_1] -> [result_1]    -- small, focused context
[tool_call_2] -> [result_2]    -- small, focused context
...
[synthesize using above]       -- results are in KV cache as structured pairs
```

Each tool result is "anchored" to its corresponding call in the
conversation history. The context never grows into a monolithic block
of unstructured text. By the time the model reaches synthesis, the data
is organized as clean `tool_call -> tool_result` pairs, not a wall of text.

### When Instruction Repetition Helps

The "Instruction Sandwich" technique (repeating key instructions at both
the top and bottom of a prompt) is effective in specific scenarios:

**Worth doing:**
- Single-shot prompts with 10K+ tokens of dense context between
  instructions and the question
- RAG retrieval where many documents are stuffed into one prompt
- Prompts where the synthesis rules are complex and easy to drift from

**Not worth doing:**
- OpenClaw cron jobs using the Spoon-Feeding Pattern (context is already
  small and structured per step)
- Interactive conversation (the model processes incrementally)
- Any prompt under ~4K tokens (attention decay is negligible)

**Token cost consideration:** Repeating instructions doubles your
instruction overhead. On cron jobs running multiple times daily, this
adds latency and cost for marginal improvement (estimated 1-3% quality
gain when the prompt is already well-structured).

### Goal-First Priming

A simpler and more token-efficient alternative to instruction repetition:
state the core objective at the very top of the prompt, before any data
or tool calls. This ensures the model processes all subsequent content
through the lens of the goal.

The Spoon-Feeding Pattern already does this -- `[SYSTEM_DIRECTIVE]` appears
first, establishing behavioral constraints before any data collection.
This is why the pattern works well even without instruction repetition.

---

## 5. Operational Procedures

### Cross-Reference Management

Workspace files reference each other. When moving content between files:

1. Identify all files that reference the content being moved
2. Move the content to the target file
3. Update ALL cross-references in source and referencing files
4. Verify with a grep for the old location to catch stale references

Common cross-reference chains:
- `AGENTS.md` <-> `SOUL.md` (boot sequence, protocols)
- `AGENTS.md` -> `TOOLS.md` (infrastructure references)
- `SOUL.md` -> `MEMORY.md` (distill & flush targets)
- `SOUL.md` -> `memory/projects.md` (project-specific memories)
- `MEMORY.md` -> `AGENTS.md` (protocol references)

### Cron Job Creation Checklist

```
[ ] Verify all CLI commands with <tool> --help (not just SKILL.md)
[ ] Use absolute paths for all file reads
[ ] One command per numbered step (atomic execution)
[ ] web_search used as native tool (not via exec)
[ ] Failure handling in SYSTEM_DIRECTIVE ([DATA UNAVAILABLE])
[ ] Payload JSON is valid (test with a JSON validator)
[ ] Total estimated execution time under 60 seconds
[ ] Model set to Flash with low thinking for cron context
```

### CLI Tool Version Upgrades

When upgrading tools used in cron jobs (or any OpenClaw skill):

1. Check new version: `<tool> --version`
2. Compare help output: `<tool> --help` and `<tool> <subcommand> --help`
3. Test all hardcoded commands from cron payloads against the new version
4. Update cron payloads if syntax changed
5. Check if the bundled SKILL.md was updated (compare against `--help`)
6. Log the version change if it affected behavior

**Why this matters:** SKILL.md files bundled with OpenClaw skills may not
update when the underlying CLI tool updates. If you trust SKILL.md blindly,
you may use deprecated flags or miss new convenience features. Always treat
`--help` as the source of truth.

### Verification Checklist

After any structural change to workspace files:

```
[ ] AGENTS.md boot steps point to valid files
[ ] AGENTS.md protocol references match SOUL.md sections
[ ] SOUL.md references to AGENTS.md match actual section headers
[ ] SOUL.md Distill & Flush targets exist (MEMORY.md, memory/projects.md)
[ ] MEMORY.md references to AGENTS.md are present and accurate
[ ] memory/projects.md references to AGENTS.md and TOOLS.md are present
[ ] HEARTBEAT.md references valid files
[ ] Cron job absolute paths match actual file locations
[ ] Cron job model assignments match AGENTS.md model section
```

---

## 6. Reference Links

### OpenClaw Documentation

| Topic | URL |
|-------|-----|
| Docs index | https://docs.openclaw.ai/llms.txt |
| Agent Workspace (file map) | https://docs.openclaw.ai/concepts/agent-workspace |
| System Prompt (injection order) | https://docs.openclaw.ai/concepts/system-prompt |
| Context (what's auto-loaded) | https://docs.openclaw.ai/concepts/context |
| Memory (search, retrieval) | https://docs.openclaw.ai/concepts/memory |
| Heartbeat | https://docs.openclaw.ai/gateway/heartbeat |
| Cron Jobs | https://docs.openclaw.ai/automation/cron-jobs |
| Skills | https://docs.openclaw.ai/tools/skills |
| Default AGENTS.md template | https://docs.openclaw.ai/reference/AGENTS.default |
| File templates | https://docs.openclaw.ai/reference/templates/* |

### Related Reading

- Causal Attention in LLMs: The architectural reason why instruction
  placement matters in prompts. Models process left-to-right; early
  context is represented without knowledge of later instructions.
- "Lost in the Middle" (Liu et al., 2023): Empirical study showing
  degraded attention to information in the middle of long contexts.
