# OpenClaw + Anthropic: Workspace & Prompt Architecture Guide

> Practical patterns for running OpenClaw with Anthropic Claude models (Claude Max plan).
> Evolved from `openclaw-gemini-guide.md` — architectural patterns are preserved,
> Gemini-specific content replaced with Anthropic equivalents.
>
> **OpenClaw docs:** https://docs.openclaw.ai/
> **Last updated:** 2026-03-01 (v3)

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
| `memory/*.md` (recent, last 7 days) | Recent session context | Boot step: scan dir, read latest | L3 |
| `memory/*.md` (older) | Historical journal archive | `memory_search` | L3 |

> **Boot pattern (2026-03-01):** Rather than reading a hardcoded `memory/YYYY-MM-DD.md`
> path (which may not exist), scan the `memory/` directory for any dated files
> within the last 7 days and read the most recent ones. This is more resilient
> than assuming a daily log exists.

> **STM is the sole source of truth for active tasks (2026-03-01):** Dated memory
> files (`memory/*.md`) and session transcript logs are **reference/intel records
> only** — they document what happened, not what is pending. Never infer active
> tasks or pending work from their content. The only place active tasks live is
> `short-term-memory.md` (L1 STM). If STM has no `[ACTIVE]` entries, there is
> nothing pending — regardless of what dated files contain.

### Content Taxonomy

| Content Type | Belongs In | NOT In |
|---|---|---|
| Operational protocols, rules, boot sequence | `AGENTS.md` | ~~MEMORY.md~~ |
| Curated facts, decisions, lessons learned (durable, timeless) | `MEMORY.md` | ~~AGENTS.md~~ |
| Time-bound intel, research outputs, event records | `memory/YYYY-MM-DD.md` | ~~MEMORY.md~~ |
| Persona, tone, vibe, journaling protocol | `SOUL.md` | |
| Identity card (name, creature, emoji) | `IDENTITY.md` | |
| User profile | `USER.md` | |
| Infrastructure (IPs, entities, paths) | `TOOLS.md` | |
| Health check protocol | `HEARTBEAT.md` | |
| Active project state | `memory/projects.md` | |
| Transactional task tracking | `short-term-memory.md` | |
| Recent session context | `memory/*.md` (last 7 days) | |

### Memory Tier Architecture

```
L1 (STM)       : short-term-memory.md      -- Active tasks, read at boot
L2 (Projects)  : memory/projects.md        -- Project context, read at boot
L3 (Search)    : memory_search             -- Searches memory/*.md + MEMORY.md
                                              Backend: QMD (BM25 + vectors + reranker)
                                              OR built-in SQLite (default)
```

### Memory Backend: QMD (Optional, Experimental)

OpenClaw's default memory backend uses a built-in SQLite vector indexer.
You can upgrade to **QMD** — a local-first search sidecar built by
[Tobi Lütke](https://github.com/tobi/qmd) that combines BM25 keyword search
+ vector embeddings + reranking, running entirely on-device via
Bun + `node-llama-cpp`.

**When to use QMD:** Memory files that contain dense exact-token data
(config keys, IDs, numbers, precise strings) alongside semantic content
benefit the most. Pure vector search misses exact tokens; QMD's BM25 layer
catches them while vectors handle meaning.

**Prerequisites:**

- `bun` runtime (install via [mise](https://mise.jdx.dev/) or `brew install bun`)
- `brew install sqlite` — extension-capable SQLite build required on macOS
- Build QMD from source (bun blocks postinstall scripts by default):

```bash
# Install from GitHub
bun install -g https://github.com/tobi/qmd

# Trust and run postinstall scripts
cd ~/.bun/install/global && bun pm trust --all

# Build the dist/ bundle (not built automatically from source)
cd ~/.bun/install/global/node_modules/@tobilu/qmd
bun install && bun run build

# Fix the binary symlink to point at the built dist
ln -sf ~/.bun/install/global/node_modules/@tobilu/qmd/dist/qmd.js ~/.bun/bin/qmd

# Verify
~/.bun/bin/qmd --version
```

**Config (`~/.openclaw/openclaw.json`):**

```json5
memory: {
  backend: "qmd",
  citations: "auto",
  qmd: {
    // Use absolute path — ~/.bun/bin is not on the gateway's PATH
    command: "/absolute/path/to/.bun/bin/qmd",
    includeDefaultMemory: true,
    update: {
      interval: "10m",       // reduce to 5m on machines with more RAM
      debounceMs: 15000,
      waitForBootSync: false  // non-blocking boot
    },
    limits: {
      maxResults: 6,
      timeoutMs: 4000
    },
    scope: {
      default: "deny",
      rules: [
        { "action": "allow", "match": { "chatType": "direct" } }
      ]
    }
  }
}
```

**Key notes:**

- `command` must be an absolute path — `~/.bun/bin` is typically not on the gateway's `PATH`.
- `waitForBootSync: false` keeps session startup non-blocking. QMD indexes in the background.
- **First search is slow:** QMD auto-downloads GGUF models (embedding + reranker) from HuggingFace on cold start. Subsequent searches are fast and fully local. On fast internet connections this is a one-time cost.
- **Graceful fallback:** If QMD fails or the binary is missing, OpenClaw automatically falls back to the built-in SQLite indexer. No hard dependency.
- **Verify the active backend:** After restart, run a `memory_search` — results will show `"provider": "qmd"` when QMD is active.
- **Memory pressure (constrained hardware):** On 8 GB unified memory systems, QMD GGUF models add ~1–1.5 GB when loaded. Set `interval: "10m"` (vs default 5 m) to reduce background refresh pressure. macOS compresses inactive pages before touching SSD swap.

---

## 2. Anthropic Model Strategy

### Model Comparison

| Aspect | Haiku | Sonnet |
|--------|-------|--------|
| Latency | Very low (~1-3s) | Low-Medium (~3-8s) |
| Cost (Max plan) | Included | Included |
| Instruction-following | Good | Excellent |
| Reasoning depth | Adequate for structured tasks | Strong — sufficient for conversation, research, and synthesis |
| Best for | Spoon-fed crons, atomic steps | Everything else: conversation, orchestration, analysis, research |

**Claude Max plan note:** On Claude Max, cost-per-call is not the primary
concern — execution time and quality are. Haiku is preferable for
timeout-constrained cron jobs because it's faster, not cheaper. Sonnet
handles all other roles including deep research and synthesis — no need
to reach for a heavier model.

### Thinking Budget Levels

Claude models support configurable thinking budgets.

| Level | When to Use | Trade-off |
|-------|-------------|-----------|
| Low | Cron jobs, atomic tool calls, spoon-fed prompts, most conversation | Fastest. Sufficient when the prompt does the thinking for the model. |
| Medium | Genuine ambiguity, multi-source conflict resolution, orchestration decisions with real stakes | Good balance for reasoning through unclear tasks. |

**Rule of thumb:** Low thinking covers the vast majority of tasks. Escalate
to medium only when the model must determine *what* to do (ambiguous
orchestration, conflicting data sources) — not just *how* to do it.

### Model Assignment Framework

Recommended assignments across OpenClaw contexts:

| Context | Model | Thinking | Rationale |
|---------|-------|----------|-----------|
| Conversation (main) | `claude-sonnet-4-6` | Low | Interactive; balanced reasoning and speed |
| Research / Deep analysis | `claude-sonnet-4-6` | Low | Sonnet handles multi-source synthesis and complex analysis without needing a heavier model |
| Cron / Automation | `claude-haiku-4-5` | Low | Spoon-fed prompts handle complexity; haiku is faster and conserves quota on bounded tasks |
| Coding (opencode) | `claude-sonnet-4-6` | Low | Via `opencode run -m anthropic/claude-sonnet-4-6` (see instance note in Section 5) |

**Cron timeout constraint:** OpenClaw cron jobs have an execution timeout
(observed ~120s in practice). For complex multi-step payloads with slow tools
(e.g., feed scanners, multiple web searches), the bottleneck is tool execution
time — not model latency. Prompt optimisation (fewer steps, smarter tool order)
is a higher-leverage fix than switching models.

**Haiku for crons (confirmed):** Haiku is the confirmed model for spoon-fed
cron jobs. The payloads already encode all reasoning — the model just executes
step-by-step. Haiku performs equivalently to sonnet on structured execution
tasks while being meaningfully faster, which reduces timeout risk on
longer-running crons.

---

## 3. Cron Job Architecture

### Isolated Agent Context

Per OpenClaw docs, isolated cron agents only receive:
- `AGENTS.md` (auto-injected)
- `TOOLS.md` (auto-injected)

They do NOT receive: SOUL.md, IDENTITY.md, USER.md, HEARTBEAT.md, MEMORY.md.
Cron payloads must be **completely self-contained** — the agent has no persona
context, no user preferences, and no memory outside of explicit file reads.

### Parallel Cron Runs

As of OpenClaw v2026.2.22, cron jobs support **parallel execution** — multiple
crons can run concurrently without queuing. This removes the hard blocking
behaviour of older versions, but scheduling discipline still matters (see
race condition gotcha below).

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
Multiple `[CRITICAL]` blocks are supported — use `[CRITICAL - <LABEL>]` for
distinct concerns (e.g., `[CRITICAL - BIRD]`, `[CRITICAL - DELIVERY]`).

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

[CRITICAL - DELIVERY]: MANDATORY FINAL STEP — After completing Phase 3,
use the message tool (action=send, channel=<channel>, target=<target>) to
deliver your full report. Do NOT truncate content.
delivery.mode: announce is fallback only.

[TOOLS]
- `exec`: For running CLI commands
- `web_search`: For internet searches (NATIVE tool, do NOT use exec)
- `read`: For reading workspace files
- `message`: For direct channel delivery (action=send, channel=<channel>, target=<target>)

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
the configured channel. Always include the prohibition in `[CRITICAL]`.

**CLI startup warnings are not failures.** Some CLIs print warnings to stdout
before returning results (e.g., permission errors for cookie stores, missing
optional dependencies). An isolated agent that sees a warning at the top of
output may incorrectly mark the step as `[DATA UNAVAILABLE]` and skip valid
results. For any CLI with known startup noise, add a `[CRITICAL - <TOOL>]`
block explaining the warning is cosmetic and results should be used if present.

**Same-minute scheduling race condition.** Two crons scheduled at the exact
same time can cause announce delivery collisions — one delivers, the other
silently drops with "cron announce delivery failed". Even with parallel run
support (v2026.2.22+), stagger schedules by at least 15 minutes when two crons
deliver to the same channel. Data still routes through session as a system
message fallback, but the user-facing announce may be lost.

**`agentId: "main"` causes announce fragility.** When a cron has
`agentId: "main"` set, its subagent completion announce routes through the
main session's WebSocket device. If that device has a scope gap or is inactive,
announces fail silently. Fix: `openclaw cron edit <id> --clear-agent`.
Spoon-fed isolated crons don't need main session context — the default agent
is always the right choice. Telegram/channel delivery uses channel adapters
directly, regardless of `agentId`.

**Session staleness after major changes.** After significant structural changes
to cron payloads or workspace files, start a new agent session before evaluating
results. Long sessions accumulate stale context.

**Announce delivery silently fails for large outputs (v2026.2.25 regression).**
The `delivery.mode: announce` path silently fails when cron output exceeds
Telegram's ~4096 character per-message limit. The delivery falls back to the
main session as a system message (shown as `deliveryStatus: "delivered"` in
`cron runs` output — misleadingly marking the main-session fallback, not
actual channel delivery). Short outputs (e.g., a few lines) continue to work.
**Fix:** Add `[CRITICAL - DELIVERY]` to the cron prompt instructing the agent
to call the `message` tool directly as its final step. The `message` tool
handles chunking natively and is not affected by this regression. Keep
`delivery.mode: announce` in place as a fallback safety net — if the
`message` tool send succeeds, announce is skipped automatically (duplicate
guard); if it fails, the announce fallback still fires.

**Slow tools still dominate runtime.** In complex multi-step crons, execution
time is driven by tool calls (feed scanners can take 30–40s alone, multiple
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

### Research Tool Orchestration

For research-heavy tasks (news analysis, geopolitical events, market data),
tool selection and sequencing significantly impacts output quality. The recommended
pattern is **parallel multi-source ingestion** followed by a single synthesis pass.
The orchestrating agent decides which tiers to fire and aggregates all results
into one coherent answer — the user sees only the synthesis, not the raw tool outputs.

**4-Tier research stack:**

| Tier | Tools | Mode | When to Use |
|------|-------|------|-------------|
| 1 | Brave (`web_search`) + Bird CLI + `exa.web_search_exa` | Always parallel | Every query. Brave=keyword/news, Bird=social signals, Exa=semantic/editorial diversity |
| 2 | `web_fetch` + `exa.crawling_exa` | Parallel, on-demand | When full article body is needed from a known URL. Both fire simultaneously. |
| 3 | `exa.web_search_advanced_exa` + `exa.company_research_exa` | On-demand, not parallel by default | Precision filters (date/domain/category) or structured company intel |
| 4 | Browser (`profile:openclaw` / `profile:chrome`) | On-demand, last resort | JS-rendered pages, interactive flows, login-gated dashboards |

**Tier 1 — always parallel:**
Fire Brave + Bird + `exa.web_search_exa` simultaneously on every research query.
No exceptions. These three tools surface different signals: Brave for speed and news
freshness, Bird for unfiltered social reactions and disinformation detection, Exa for
semantic match and non-dominant editorial angles.

**Breaking event rule (MANDATORY):** For any breaking event <48h old — fire Brave +
Bird + Exa as one parallel block. Do not fire Brave-only and call it done. Breaking
events are where all three signals diverge most: Brave catches wire headlines, Bird
catches unfiltered reactions and disinformation, Exa surfaces editorial analysis from
sources Brave doesn't rank highly.

**Query pattern — anchor + angle:** Never fire two near-identical queries in parallel.
One query anchors the core fact (`event + key actors + outcome`); the parallel query
chases a specific POV, counter-argument, or data source (`"expert analysis"`,
`"institutional response"`, `"economic impact"`). Anchor + angle extracts more signal
from the same number of tool calls.

**Tier 2 — URL extraction, parallel:**
When you need the full body of a specific article, fire `web_fetch` and
`exa.crawling_exa` simultaneously. Take whichever returns better content.
`exa.crawling_exa` handles paywalled and JS-heavy pages better than `web_fetch`
(e.g. bypasses Reuters 401 errors, returns complete Medium articles where `web_fetch`
truncates). `web_fetch` is faster on clean, non-paywalled pages.

> **X.com exception:** Both `web_fetch` and `exa.crawling_exa` are blocked on
> x.com/twitter.com — `web_fetch` returns a login wall, `exa.crawling_exa` is
> banned by the domain. Bird CLI (Tier 1) is the only correct tool for X content.
> Do not fire Tier 2 on X.com URLs.

**Proactive content-type trigger (MANDATORY):** Do not wait for a full URL to fire
Tier 2. When Tier 1 surfaces a snippet from a high-value source — institutional
reports (RAND, CSIS, Brookings, Pentagon, INSS), paywalled journalism (NYT, FT,
Foreign Affairs), academic papers — fire `exa.crawling_exa` proactively to extract
the full document. Snippet-level data from these sources is consistently insufficient
for synthesis. The proactive trigger is content-type based, not failure-based.

**Deep Research Mode:** In sessions with 3+ research turns requiring depth (geopolitical
analysis, multi-source synthesis, technical deep-dives) — default every institutional
source hit to a Tier 2 crawl alongside Tier 1 search. The quality ceiling of
snippet-only research is meaningfully lower than full-document synthesis for these
session types.

**Tier 3 — on-demand precision:**
- `exa.web_search_advanced_exa`: date filters (`startPublishedDate`), domain
  restrictions (`includeDomains`), category filters (`"news"`, `"financial report"`,
  `"research paper"`). Trigger when precision matters more than speed.
- `exa.company_research_exa`: structured company profile — headcount, funding
  history, tech stack, competitors, key executives. Trigger on explicit due diligence
  questions. NOT for breaking news about a company (Tier 1 covers that).

**Tier 4 — interactive/visual, last resort:**
- `profile:openclaw`: isolated browser, no saved logins. Use for public JS-rendered
  pages where lower tiers return empty content — e.g. live trading charts, SPAs,
  public dashboards with dynamic content.
- `profile:chrome`: your active Chrome session with existing cookies. Use for
  login-gated pages. Requires the user to attach the tab via the Browser Relay
  toolbar button first.

**Decision flow:**
```
Any query →
  Always fire Tier 1 (Brave + Bird + Exa search) in parallel

  Need full article from a URL?
  → Fire Tier 2 (web_fetch + crawling_exa) in parallel
  → URL is X.com? → Skip Tier 2, Bird already covered it in Tier 1

  Need date/domain/category precision?
  → Fire web_search_advanced_exa (Tier 3)

  Need company structure/funding/headcount?
  → Fire company_research_exa (Tier 3)

  Content is JS-rendered or requires login?
  → Fire Browser (Tier 4)
  → Needs session auth? → profile:chrome, user must attach tab
```

**Why the orchestrator synthesizes, not the tools:**
The agent fires all relevant tiers, reads all results, and delivers one coherent
answer. This mirrors the experience of products like Google AI Mode or Exa Deep
Research, but with added context-awareness (user history, prior decisions) and
social signal integration via Bird that neither product provides natively.

---

## 5. Coding Architecture

### Skill-First Approach

Coding tasks are delegated via the **coding-agent skill** rather than raw
command invocations. The skill owns the HOW (PTY, background mode, process
monitoring, auto-notify on completion); the orchestrator (AGENTS.md) owns the
project-level constraints.

**Read the skill's SKILL.md before spawning a coding task.** It contains
current command syntax, PTY requirements, and background monitoring patterns
that may change with OpenClaw updates. Hardcoding CLI syntax in AGENTS.md
creates maintenance debt.

**Preferred agent:** `opencode` via Anthropic provider (`claude-sonnet-4-6`, Thinking: Low).
Other supported agents: Codex, Claude Code (`claude`), Pi.

> **Instance Note (2026-02-23):** Anthropic direct OAuth is broken in this deployment.
> Working path: **Google Vertex ADC**. Model: `google-vertex-anthropic/claude-sonnet-4-6@default`.
> Config in `~/.config/opencode/opencode.json`: set your GCP `project` and
> `location: us-east5` (Claude Sonnet 4.x unavailable in `us-central1` or `global`).
> Auth via Application Default Credentials (ADC).
> This is a deployment-specific workaround — the generic Anthropic provider pattern above
> remains correct for setups where OAuth is functional.

**Key rules (orchestrator-level — put these in AGENTS.md, not the skill):**
- Planning stays at orchestrator level — present a plan, get approval, then delegate to skill
- `git init` always. Local commits only. No `git push` without explicit user action
- Local unit/functional tests with mocks. No external deps
- Project root: your preferred git directory (e.g., `~/Developer/git/`)

**Why skill-first over raw commands:**
- Skill stays up-to-date with OpenClaw releases (PTY flags, auto-notify pattern, etc.)
- Decouples orchestrator from implementation detail
- Single source of truth for HOW; AGENTS.md only carries project constraints

---

## 6. MCP Tools Integration

OpenClaw supports Model Context Protocol (MCP) servers via the
**[mcporter](http://mcporter.dev)** CLI. This lets you call external tools,
APIs, and data sources from within agent context — in both interactive sessions
and cron job payloads.

### Installing mcporter

```bash
npm install -g mcporter
# or
bun install -g mcporter
```

Verify: `mcporter --version`

### Configuration

mcporter reads from `./config/mcporter.json` by default (relative to your
workspace root). Override with `--config /path/to/config.json`.

**Config structure:**

```json
{
  "mcpServers": {
    "<server-name>": {
      "baseUrl": "https://your-mcp-server-endpoint",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

For stdio-based (local process) servers:

```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "bun run /path/to/server.ts"
    }
  }
}
```

### Core Commands

```bash
# List all configured servers and their tools
mcporter list

# Inspect a server's available tools and schema
mcporter list <server-name> --schema

# Call a tool (key=value syntax)
mcporter call "<server-name>.<tool-name>" param="value"

# Call a tool (JSON payload)
mcporter call "<server-name>.<tool-name>" --args '{"param": "value"}'

# Machine-readable output
mcporter call "<server-name>.<tool-name>" param="value" --output json
```

### Example: HTTP MCP Server (Google Developer Knowledge)

The [Google Developer Knowledge MCP](https://github.com/googlecloudplatform/google-dev-knowledge-mcp)
is a remote HTTP server that provides semantic search over official Google
developer documentation (GCP, Firebase, Android, Gemini APIs, Maps, etc.).

**Config (`<workspace>/config/mcporter.json`):**

```json
{
  "mcpServers": {
    "google-dev-knowledge": {
      "baseUrl": "https://developerknowledge.googleapis.com/mcp",
      "headers": {
        "X-Goog-Api-Key": "YOUR_GOOGLE_API_KEY"
      }
    }
  }
}
```

**Available tools:**

| Tool | Description |
|------|-------------|
| `search_documents` | Semantic search across all indexed Google docs |
| `get_document` | Fetch a specific document by ID |
| `batch_get_documents` | Fetch multiple documents by ID |

**Usage:**

```bash
# Search Google developer docs
mcporter call "google-dev-knowledge.search_documents" query="Cloud Run cold start optimization"

# Fetch a specific document
mcporter call "google-dev-knowledge.get_document" id="<document-id>"
```

### Using MCP Tools in Agent Context

Once configured, reference MCP tools in cron payloads or interactive tasks
using the `exec` tool (mcporter is a shell CLI):

```
Step N: exec: mcporter call "google-dev-knowledge.search_documents" query="your query here" --output json
```

**Spoon-feeding rules still apply:**
- One `mcporter call` per numbered step
- Use `--output json` for structured results the agent can parse
- Hardcode the full `mcporter call` command with absolute config path if running
  from a cron (isolated agent has no working directory):

```
exec: mcporter --config /absolute/path/to/config/mcporter.json call "server.tool" param="value"
```

### MCP in TOOLS.md

Document active MCP servers in `TOOLS.md` so agents can reference them:

```markdown
## MCP Tools (mcporter)
- Config: `<workspace>/config/mcporter.json`
- Active Servers:
  - `google-dev-knowledge` — Google Developer docs (GCP, Firebase, Gemini APIs, etc.)
    Tools: search_documents, get_document, batch_get_documents
    Usage: `mcporter call "google-dev-knowledge.search_documents" query="..."`
```

---

## 7. Operational Procedures

### Cron Job Creation Checklist

```
[ ] Verify all CLI commands with <tool> --help (not just SKILL.md)
[ ] Use absolute paths for all file reads
[ ] One command per numbered step (atomic execution)
[ ] web_search used as native tool (not via exec)
[ ] Failure handling in SYSTEM_DIRECTIVE ([DATA UNAVAILABLE])
[ ] Total estimated execution time well under ~120s timeout
[ ] NO_REPLY guard in [CRITICAL] block for announce delivery jobs
[ ] [CRITICAL - DELIVERY] block added with message tool instruction (channel + target hardcoded)
[ ] For CLIs with known startup warnings, add [CRITICAL - <TOOL>] guard explaining noise
[ ] Model set to haiku with low thinking (confirmed for spoon-fed crons)
[ ] Schedules staggered ≥15min apart from other crons delivering to the same channel
[ ] agentId NOT set to "main" (use default agent for isolated crons)
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
[ ] QMD binary accessible (if enabled): run memory_search and confirm provider: "qmd"
[ ] MCP server configs in mcporter.json verified with mcporter list
```

### CLI Tool Version Upgrades

When upgrading tools used in cron jobs:
1. Check new version: `<tool> --version`
2. Compare help: `<tool> --help` and `<tool> <subcommand> --help`
3. Test all hardcoded cron commands against the new version
4. Update cron payloads if syntax changed
5. Always treat `--help` as source of truth, not SKILL.md

---

## 8. Reference Links

| Topic | URL |
|-------|-----|
| OpenClaw Docs | https://docs.openclaw.ai/ |
| Agent Workspace | https://docs.openclaw.ai/concepts/agent-workspace |
| System Prompt | https://docs.openclaw.ai/concepts/system-prompt |
| Cron Jobs | https://docs.openclaw.ai/automation/cron-jobs |
| Skills | https://docs.openclaw.ai/tools/skills |
| Memory (QMD backend) | https://docs.openclaw.ai/concepts/memory |
| mcporter | http://mcporter.dev |
| QMD (Tobi Lütke) | https://github.com/tobi/qmd |

---

## 9. Revision History

| Date | Change |
|------|--------|
| 2026-03-01 (v3) | Section 1: Added STM-as-sole-task-source-of-truth rule (dated files are reference/intel only, not task queues). Clarified Content Taxonomy: time-bound intel/research outputs route to `memory/YYYY-MM-DD.md`, not `MEMORY.md`. Section 4: Added Breaking Event Rule (mandatory Brave+Bird+Exa triple parallel for events <48h old). Added Anchor+Angle query pattern (never two near-identical parallel queries). Added Proactive Content-Type Tier 2 trigger (fire `crawling_exa` on institutional/paywalled sources without waiting for a known URL). Added Deep Research Mode (3+ research turns → default every institutional source to Tier 2 crawl). |
| 2026-03-01 (v2) | Section 4: Full rewrite of Research Tool Orchestration — upgraded to complete 4-tier architecture. Tier 1: Brave+Bird+Exa search always parallel. Tier 2: web_fetch+crawling_exa parallel URL extraction with X.com exception documented (both tools blocked on x.com, Bird is correct tool). Tier 3: web_search_advanced_exa (precision filters) + company_research_exa (structured company intel) on-demand. Tier 4: Browser with two profiles — profile:openclaw (public JS pages) vs profile:chrome (login-gated, requires Browser Relay attach). Added decision flow pseudocode and orchestrator synthesis rationale. |
| 2026-03-01 | Section 2: Removed Opus from model strategy — Sonnet is now the default for all roles including research and deep analysis. Simplified Thinking Budget table (removed High tier). Updated Model Assignment Framework table accordingly. Section 1: Updated On-Demand Files boot pattern — replaced hardcoded `YYYY-MM-DD.md` with resilient "scan last 7 days" approach. Section 4: Added Research Tool Orchestration subsection — documents Brave+Bird parallel (Tier 1), Exa for breaking events (Tier 2), web_fetch for verification (Tier 3), Browser for interactive (Tier 4); includes breaking events parallel execution rule and rationale for each tier's placement. |
| 2026-02-27 | Section 3: Added `[CRITICAL - DELIVERY]` block to Payload Skeleton and `[TOOLS]` section. Added new Common Gotcha: announce delivery silently fails for large outputs (v2026.2.25 regression) — `message` tool is the reliable fix, `delivery.mode: announce` retained as fallback. Updated `[CRITICAL]` description to document labeled blocks pattern. Added `[CRITICAL - DELIVERY]` to Cron Job Creation Checklist. |
| 2026-02-25 | Instance-specific config notes added (no generic pattern changes). Section 5: added instance note block — Anthropic direct OAuth broken, working path is Google Vertex ADC (`google-vertex-anthropic/claude-sonnet-4-6@default`, `us-east5`). Section 2 model table: linked coding row to Section 5 note. TOOLS.md addition: Gemini CLI section added as a headless analytics proxy layer (taxonomy-correct, no guide changes needed). Confirmed all 7 workspace files aligned to guide taxonomy after audit. |
| 2026-02-23 | Added QMD memory backend subsection (Section 1): install pattern, config, memory pressure notes, updated L3 tier diagram. Updated model assignment table: haiku confirmed for crons (resolved backlog item). Added two cron gotchas: same-minute scheduling race condition and `agentId: "main"` fragility. Added parallel cron support note (v2026.2.22). Added new Section 6: MCP Tools Integration via mcporter — config pattern, core commands, HTTP/stdio server examples, google-dev-knowledge reference, agent usage pattern. Updated operational checklists. Added QMD + mcporter reference links. Renumbered sections 6→7 (Operational), 7→8 (Reference Links), 8→9 (Revision History). |
| 2026-02-20 | Skill-first coding: Section 5 updated to delegate via coding-agent skill instead of raw opencode command. Added CLI startup warning pattern to Section 3 gotchas and Section 6 checklist. |
| 2026-02-19 | Initial creation. Forked from `openclaw-gemini-guide.md`. Replaced Gemini model strategy with Anthropic. Updated model assignments, coding architecture, and cron notes to reflect Claude Max migration. |
