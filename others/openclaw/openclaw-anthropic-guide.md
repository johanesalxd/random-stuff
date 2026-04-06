# OpenClaw: Workspace & Prompt Architecture Guide

> Practical patterns for running OpenClaw in a personal workspace: agent architecture,
> memory layout, research/coding flows, cron design, and operational guardrails.
>
> Historical note: this file keeps the old `openclaw-anthropic-guide.md` filename for
> continuity, but the guide content is now provider-agnostic.
>
> **OpenClaw docs:** https://docs.openclaw.ai/
> **Last updated:** 2026-04-06 (v15)

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
| `TOOLS.md` | Infrastructure notes, entity IDs, paths, device references. **Does NOT control tool availability — guidance only.** | Yes |
| `HEARTBEAT.md` | Periodic health check checklist. **Keep short — token burn risk on every heartbeat poll.** | No |
| `MEMORY.md` | Curated long-term memory (decisions, preferences, lessons) | No |

**Key distinction:** Sub-agents and isolated cron agents only receive
`AGENTS.md` + `TOOLS.md`. This is why cron payloads must be self-contained
— the agent cannot rely on persona, user profile, or memory files.

### PROTOCOLS.md (Triggered Procedure Store)

The live workspace centralizes triggered protocol details in `PROTOCOLS.md` at the
workspace root. This file is NOT auto-injected — it is read on demand when a protocol
is triggered by name. It contains the authoritative step-by-step procedures for:

- Distill & Flush Protocol
- Spa Day (Context Optimization) Protocol
- Research Modes & llm-wiki Invocation Policy
- Coding Task Protocol (Orchestrator Loop)

Deep Analysis itself now lives in the dedicated `deep-analysis` skill, not inside
`PROTOCOLS.md`.

The guide's inline descriptions of these protocols are public-facing summaries.
`PROTOCOLS.md` is the source of truth for operational detail in a live workspace.
`AGENTS.md` references it explicitly in its prework steps.

### One-Time / Restart Files

These files serve specific lifecycle events — not injected on every session turn.

| File | Purpose | When It Fires |
|------|---------|---------------|
| `BOOT.md` | Optional startup checklist. Keep short; use `message` tool for outbound sends. | On **gateway restart** (internal hooks must be enabled). Distinct from `HEARTBEAT.md`. |
| `BOOTSTRAP.md` | One-time first-run ritual. Delete it after completion — it is only created for brand-new workspaces. | On **first boot** only. If present, agent reads it, follows it, then deletes it. |

> **BOOT.md vs HEARTBEAT.md:** `BOOT.md` fires on gateway restart. `HEARTBEAT.md` fires on heartbeat polls. Two separate files, two separate triggers — do not conflate.

### Workspace Directories

| Path | Purpose | Notes |
|------|---------|-------|
| `skills/` | Workspace-specific skills | Load order (highest to lowest): (1) `<workspace>/skills/<name>/SKILL.md` — workspace-specific (this directory, highest precedence); (2) `<workspace>/.agents/skills/<name>/SKILL.md` — workspace-agent; (3) `~/.agents/skills/<name>/SKILL.md` — agent-shared; (4) `~/.openclaw/skills/<name>/SKILL.md` — managed/global; (5) OpenClaw bundled skills; (6) `skills.load.extraDirs` / other low-precedence injected skill dirs. When names collide, higher-tier entry wins. |
| `canvas/` | Canvas UI files for node displays | e.g. `canvas/index.html`. Optional. |
| `memory/` | All dated logs, project context, archives | Indexed by QMD. Not injected automatically — read via boot sequence or `memory_search`. |

### Skills Registry: ClawHub

Browse and install community skills at https://clawhub.com — the public skills
registry for OpenClaw.

```bash
# Install a skill into your workspace
clawhub install <skill-slug>

# Update all installed skills
clawhub update --all

# Sync (scan local skills + publish)
clawhub sync --all
```

Skills install into `./skills` under your workspace root by default, giving them
the highest precedence in the load order.

**SKILL.md frontmatter gotcha:** quote values containing `:` or non-ASCII characters,
and keep frontmatter keys single-line. Silent YAML/frontmatter parse breakage is a real
failure mode in live workspaces.

### Non-Standard Files (loaded via boot sequence)

These files are NOT auto-injected. The boot sequence in `AGENTS.md` must
explicitly instruct the agent to read them at session start.

| File | Purpose | Memory Tier |
|------|---------|-------------|
| `short-term-memory.md` | Transactional task state tracking | L1 (STM) |
| `memory/projects.md` | Project context, active state | L2 (Persistent context) |

### On-Demand Files (searched, not loaded at boot)

| Path | Purpose | Access Method | Memory Tier |
|------|---------|---------------|-------------|
| `memory/*.md` (recent, last 48h) | Recent session context | Boot step: read today's + yesterday's dated file | L2 |
| `memory/*.md` (older) | Historical journal archive | `memory_search` | L2 |

> **Boot pattern (2026-03-04):** Read today's and yesterday's main dated files
> (`memory/YYYY-MM-DD.md`) if they exist. If none within 48h, read the single
> most recent one. Sub-files (e.g. `2026-03-02-session-name.md`) are auto-generated
> session transcripts — skip at boot, available via `memory_search` if needed.
> These files are L2 (persistent context); `memory_search` is the retrieval mechanism for L2+L3.

> **STM is the sole source of truth for active tasks (2026-03-01):** Dated memory
> files (`memory/*.md`) and session transcript logs are **reference/intel records
> only** — they document what happened, not what is pending. Never infer active
> tasks or pending work from their content. The only place active tasks live is
> `short-term-memory.md` (L1 STM). If STM has no `[ACTIVE]` entries, there is
> nothing pending — regardless of what dated files contain.

### Workspace File Injection Architecture

```mermaid
graph LR
    subgraph Auto["Auto-injected every turn"]
        AGENTS["AGENTS.md\nProtocols + boot sequence"]
        SOUL["SOUL.md\nPersona + tone"]
        IDENTITY["IDENTITY.md\nName + role"]
        USER["USER.md\nUser profile"]
        TOOLS["TOOLS.md\nInfra + entity IDs"]
        HEARTBEAT["HEARTBEAT.md\nHealth check"]
        MEMORY["MEMORY.md\nCurated long-term memory"]
    end

    subgraph Boot["Read at boot (explicit)"]
        STM["short-term-memory.md\nL1 Active tasks"]
        PROJ["memory/projects.md\nL2 Project context"]
        DATED["memory/YYYY-MM-DD.md\nL2 Recent dated files"]
    end

    subgraph OnDemand["On-demand via memory_search (retrieves L2+L3)"]
        SEARCH["memory/*.md + MEMORY.md\nHistorical archive"]
    end

    Main["Main Agent"] --> Auto
    Main --> Boot
    Main --> OnDemand

    Cron["Cron / Sub-agent\n(isolated)"] --> AGENTS
    Cron --> TOOLS
```

> **Key rule:** Cron and sub-agents only receive `AGENTS.md` + `TOOLS.md`.
> All other context must be spoon-fed explicitly in the cron payload.

### Content Taxonomy

| Content Type | Belongs In | NOT In |
|---|---|---|
| Operational protocols, rules, boot sequence | `AGENTS.md` | ~~MEMORY.md~~ |
| Curated facts, decisions, lessons learned (durable, timeless) | `MEMORY.md` (L3 — auto-injected) | ~~AGENTS.md~~ |
| Time-bound intel, research outputs, event records | `memory/YYYY-MM-DD.md` (L2) | ~~MEMORY.md~~ |
| Archived detail from context optimization | `memory/YYYY-MM-DD-memory-archive.md` (L2) | ~~MEMORY.md~~ |
| Persona, tone, vibe, journaling protocol | `SOUL.md` | |
| Identity card (name, creature, emoji) | `IDENTITY.md` | |
| User profile | `USER.md` | |
| Infrastructure (IPs, entities, paths) | `TOOLS.md` | |
| Health check protocol | `HEARTBEAT.md` | |
| Active project state | `memory/projects.md` (L2) | |
| Transactional task tracking | `short-term-memory.md` (L1) | |
| Recent session context | `memory/*.md` (last 48h, L2) | |

### Memory Tier Architecture

```mermaid
graph TD
    Boot["Session Boot"] --> L1["L1 — STM\nshort-term-memory.md\nActive tasks · read at boot"]
    Boot --> L2["L2 — Persistent context\nmemory/ folder\nprojects.md + dated files\n(project-scoped vs session-scoped\nis organizational, not a tier boundary)"]
    Boot --> L3["L3 — Curated durables\nMEMORY.md\nAuto-injected every turn\nDecisions, lessons, preferences"]

    Recall["memory_search\n(retrieval mechanism for L2+L3)"] --> QMD["QMD backend\nBM25 + vectors + reranker\n(optional, experimental)"]
    Recall --> SQLite["Built-in SQLite\n(default)"]

    style L1 fill:#d4edda,stroke:#28a745
    style L2 fill:#d1ecf1,stroke:#17a2b8
    style L3 fill:#fff3cd,stroke:#ffc107
    style Recall fill:#f8f9fa,stroke:#6c757d
    style QMD fill:#f8f9fa,stroke:#6c757d
    style SQLite fill:#f8f9fa,stroke:#6c757d
```

> **memory_search** is the retrieval mechanism that searches L2 + L3 on demand — not a tier itself.

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
# Install latest published package
bun install -g @tobilu/qmd

# Verify
~/.bun/bin/qmd --version

# If native bindings fail after install (common on bun because postinstall is blocked)
cd ~/.bun/install/global/node_modules/better-sqlite3
npm run build-release
```

**Config (`~/.openclaw/openclaw.json`):**

```json5
memory: {
  backend: "qmd",
  citations: "auto",
  qmd: {
    // Use absolute path — ~/.bun/bin is not on the gateway's PATH
    command: "/absolute/path/to/.bun/bin/qmd",
    includeDefaultMemory: false,
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
        { "action": "allow", "match": { "chatType": "direct" } },
        { "action": "allow", "match": { "rawKeyPrefix": "agent:main:subagent:" } },
        { "action": "allow", "match": { "rawKeyPrefix": "agent:vader-yolo:subagent:" } }
      ]
    }
  }
}
```

**Key notes:**

- `includeDefaultMemory: false` prevents the default memory context from bleeding across
  unrelated sessions. Set to `true` if you want the model's default memory available in
  all sessions, but `false` is the recommended default for scoped multi-session workspaces.
- `command` must be an absolute path — `~/.bun/bin` is typically not on the gateway's `PATH`.
- `waitForBootSync: false` keeps session startup non-blocking. QMD indexes in the background.
- **First search is slow:** QMD auto-downloads GGUF models (embedding + reranker) from HuggingFace on cold start. Subsequent searches are fast and fully local. On fast internet connections this is a one-time cost.
- **Graceful fallback:** If QMD fails or the binary is missing, OpenClaw automatically falls back to the built-in SQLite indexer. No hard dependency.
- **Verify the active backend:** After restart, run a `memory_search` — results will show `"provider": "qmd"` when QMD is active.
- **Health check:** Use `openclaw memory status` — not `qmd status`. The `qmd` CLI maintains a separate database (`~/.cache/qmd/`) unrelated to the OpenClaw-managed instance (`~/.openclaw/agents/main/qmd/`). Only `openclaw memory status` reflects what actually powers `memory_search`. Key fields to check: `provider: "qmd"`, `dirty: false`, `files > 0`.
- **Memory pressure (constrained hardware):** On 8 GB unified memory systems, QMD GGUF models add ~1–1.5 GB when loaded. Set `interval: "10m"` (vs default 5 m) to reduce background refresh pressure. macOS compresses inactive pages before touching SSD swap.

#### QMD Query Strategy

QMD's BM25 semantic search layer prefers **short, keyword-driven queries
(2–4 words)**. Verbose multi-part queries or boolean-style logic fail
silently — returning 0 results without error. This is not a bug; it's how
BM25 tokenization works.

**The failure mode:** An agent issues a complex query like
`"memory architecture BM25 search configuration state directory"` →
QMD returns 0 results → the agent assumes the data doesn't exist and
reports "not found." The data is there; the query pattern is wrong.

**Workaround:** Break complex recall needs into 2–3 atomic searches:
- ❌ `"memory architecture BM25 search configuration state directory"`
- ✅ `"QMD config"` + `"memory indexing"` (separate searches)

**Why this matters for haiku/sonnet-class models:** These models have tighter
effective context budgets than opus-class. Tighter queries = faster QMD
lookups + more room for task context in the window. This strategy is also
critical for cron agents and sub-agents that receive minimal boot context.

**Practical guidance for AGENTS.md:** Add a mid-session recall rule — when
the user asks about a prior decision or config that isn't in the current
injection window, fire `memory_search` with short keyword queries before
answering. If 0 results on first attempt, refire with different keywords
before concluding the data is missing.

**QMD search mode:** Use the `search` command (BM25, fast). The `vsearch`
(vector-only) and `query` (hybrid) modes are unreliable on memory-constrained
hardware — poor accuracy and significantly slower. On 8 GB unified memory
systems in particular, stick to BM25 `search` as the default. Hybrid search
may improve on higher-spec machines as QMD matures.

### Memory Tools

OpenClaw exposes two agent-facing tools for memory files:

- **`memory_search`** — semantic recall over indexed snippets (BM25 + optional vector).
  Use when you need to find relevant content across `memory/*.md` and `MEMORY.md` by
  topic or keyword. Prefers short 2–4 word keyword queries (see QMD Query Strategy above).

- **`memory_get`** — targeted read of a specific Markdown file or line range.
  Use when you know the exact file path (e.g. today's dated log, a specific project file).
  Degrades gracefully when a file doesn't exist — returns empty string, not an error.
  This makes it safe to call for today's dated file even before the first write of the day.

**Rule of thumb:** Use `memory_search` for discovery (what exists?); use `memory_get`
for retrieval (read this specific file).

### Context Optimization & Memory Compaction

As workspace memory grows over weeks of use, boot context bloats —
eventually causing **silent truncation** of injected files. OpenClaw enforces
a per-file injection limit (`bootstrapMaxChars`, default 20,000 chars). Content
beyond that limit is silently dropped, meaning the agent loses access to lessons
and decisions without any error.

**Targets:**
- Boot context (all auto-injected files): **< 60KB**
- MEMORY.md: **< 15KB** (well under the per-file injection limit)
- Zero truncation of any injected file

**Injection limits (official):**
- Per-file cap: `agents.defaults.bootstrapMaxChars` = **20,000 chars** (default). Content beyond this is silently dropped.
- Aggregate cap: `agents.defaults.bootstrapTotalMaxChars` = **150,000 chars** (default). Total across all injected files.
- Both are configurable in `~/.openclaw/openclaw.json` if you need higher limits.

**The Archive Convention:**

When MEMORY.md or other injected files grow too large, move detailed
content to dated archive files:

```
memory/YYYY-MM-DD-memory-archive.md
```

These archives are NOT injected on every turn, but remain fully searchable
via `memory_search` (QMD indexes all files in `memory/`). This preserves
access while reducing boot context.

**memoryFlush configuration:**

OpenClaw's compaction pipeline includes a `memoryFlush` step that writes
durable notes to disk before compaction summarizes the conversation history.
The key config is `softThresholdTokens` — the token count at which
memoryFlush fires *before* compaction begins.

```json5
// ~/.openclaw/openclaw.json
"agents": {
  "defaults": {
    "compaction": {
      "memoryFlush": {
        "softThresholdTokens": 15000
      }
    }
  }
}
```

**Why 15,000?** A single large tool response (web fetch, financial data, long
exec output) can jump 3–8k tokens in one turn. If `softThresholdTokens` is
set too low (e.g., 4,000), a single large response can push the context past
the threshold and straight into compaction — skipping the memoryFlush step
entirely. The result: durable notes that should have been written to disk are
instead compacted into the session summary and eventually lost.

Setting `softThresholdTokens: 15000` gives a reliable pre-compaction write
window. Tune upward if your sessions routinely use tools that return very
large payloads.

**Compaction Workflow (Distill & Flush):**

When transactional state (STM) becomes bloated or a session involves
many decisions, execute this compaction sequence:
1. Write any active discussion or decision-in-flight → STM as a new
   `## Active Context: <Topic>` section
2. Move settled lessons, behavioral rules, tool quirks →
   `MEMORY.md` (Lessons Learned). Only durable, timeless content.
3. Move time-bound intelligence, research outputs, event records →
   `memory/YYYY-MM-DD.md` (today's date). Dated snapshots, not permanent.
4. Move project-specific outcomes, status changes →
   `memory/projects.md`
5. Trim STM: remove `[DONE]` tasks older than 2–3 entries, stale notes
6. Confirm to user. Fresh session boot reconstructs from distilled files.

**Measurement:** Use `wc -c` on all workspace files to measure actual
boot context size. Run periodically (weekly or when sessions feel sluggish).

### Session Reset Configuration

OpenClaw supports automatic session resets to prevent stale context
accumulation. Configuration lives at the **top level** of
`~/.openclaw/openclaw.json` — NOT inside `agents.defaults`.

```json5
// ✅ Correct — top level
{
  "session": {
    "reset": {
      "mode": "idle",        // or "daily"
      "idleMinutes": 2880    // only for mode: "idle"
      // "atHour": 4         // only for mode: "daily" (24h format, local tz)
    }
  }
}

// ❌ Wrong — inside agents.defaults (silently ignored)
{
  "agents": {
    "defaults": {
      "session": { "reset": { ... } }  // does nothing
    }
  }
}
```

**Available modes:**

| Mode | Behavior | Use Case |
|------|----------|----------|
| `daily` | Resets at `atHour` (default: 4 AM local time) every day | Predictable daily fresh start |
| `idle` | Resets after `idleMinutes` of no messages | Preserves active sessions, clears stale ones |

There is no `"none"` or `"manual"` mode. If you want minimal resets,
use `idle` with a high `idleMinutes` value (e.g., 2880 = 2 days).

**Model override scoping:** Model overrides set via `/model` or
`session_status` are **session-scoped** — they do not persist across
resets. Only `agents.defaults.model.primary` in `openclaw.json`
survives a session reset. Plan accordingly when temporarily switching
models.

---

## 2. Model Strategy (Provider-Agnostic)

### Model Providers

OpenClaw supports multiple providers at the same time. In practice, a healthy
personal-assistant setup usually keeps at least three lanes available:

| Provider lane | Auth method | Best for |
|---|---|---|
| GitHub Copilot | `openclaw models auth login-github-copilot` | Low-friction daily-driver GPT / Claude / Grok access through the Copilot subscription |
| Anthropic direct or Anthropic via Vertex | OAuth, API key, or Google ADC | Claude-native paths, stronger fallback diversity, and provider redundancy |
| Google / local / third-party providers | API key, ADC, or local server | Gemini workflows, local LM Studio / Ollama fallback, or specialized models |

**Practical takeaway:** keep aliases stable and swap provider targets behind them. That lets
you change providers without rewriting prompts, cron payloads, or session conventions.

### Model Aliases

OpenClaw supports user-defined aliases in `~/.openclaw/openclaw.json`.
Aliases let you treat models as roles instead of hardcoded provider IDs.

```json5
"agents": {
  "defaults": {
    "models": {
      "github-copilot/gpt-5.4-mini": { "alias": "gpt54min" },
      "github-copilot/gpt-5.4": { "alias": "gpt54" },
      "github-copilot/gpt-5-mini": { "alias": "gpt5min" },
      "github-copilot/grok-code-fast-1": { "alias": "grok" },
      "github-copilot/claude-haiku-4-5": { "alias": "haiku-gh" },
      "github-copilot/claude-sonnet-4-6": { "alias": "sonnet-gh" },
      "anthropic/claude-sonnet-4-6": { "alias": "sonnet" },
      "anthropic/claude-haiku-4-5": { "alias": "haiku" },
      "anthropic/claude-opus-4-6": { "alias": "opus" },
      "anthropic-vertex/claude-sonnet-4-6": { "alias": "sonnet-av" },
      "anthropic-vertex/claude-opus-4-6": { "alias": "opus-av" },
      "google/gemini-3-flash-preview": { "alias": "gemini-flash" },
      "google/gemini-3.1-pro-preview": { "alias": "gemini-pro" },
      "openrouter/deepseek/deepseek-v3.2": { "alias": "deepseek" },
      "openrouter/moonshotai/kimi-k2.5": { "alias": "kimi" },
      "openrouter/minimax/minimax-m2.5": { "alias": "minimax" },
      "lmstudio/qwen3.5-35b-a3b": { "alias": "qwen-local" }
    }
  }
}
```

> **Config structure note:** aliases live under
> `agents.defaults.models[<full-model-id>].alias`, not the older flat `models.aliases` map.

Use aliases in cron payloads, `sessions_spawn`, and `/model` overrides.
If a provider changes its public model ID, you update one alias target and the
rest of the workspace stays stable.

The table above is illustrative, not mandatory canon. Real workspaces often carry more
aliases than they use daily; document the stable operational ones and keep the rest as
available fallbacks.

### Model Comparison

| Role | Typical aliases | Best for |
|---|---|---|
| Daily driver | `gpt54min`, `sonnet` | Main conversation, routine orchestration, most research and planning |
| Escalation / harder judgment | `gpt54`, `sonnet`, `opus`, `opus-av` | Contested decisions, deeper synthesis, tougher orchestration calls |
| Cheap atomic / throwaway | `gpt5min`, `haiku` | Short disposable tasks, simple cron work, low-stakes structured execution |
| Local fallback | `qwen-local` | Offline-ish recovery path, local experimentation, resilience |

**Recommended policy:** choose one reliable low-cost daily-driver alias as the workspace default,
keep one or two stronger escalation aliases for harder judgment, and reserve the cheapest models
for throwaway or tightly spoon-fed tasks.

### Thinking Budget Levels

Claude models support configurable thinking budgets. **Adaptive thinking
is the default** for Claude 4.6 models when no explicit thinking level is
configured. If you have no explicit `thinking` setting in your config, your
agent is running adaptive (variable token usage per turn).

| Level | When to Use | Trade-off |
|-------|-------------|-----------|
| Low | Cron jobs, atomic tool calls, spoon-fed prompts, most conversation | Fastest. Sufficient when the prompt does the thinking for the model. Explicit `thinking: low` in config overrides the adaptive default. |
| Medium | Genuine ambiguity, multi-source conflict resolution, orchestration decisions with real stakes | Good balance for reasoning through unclear tasks. |
| Adaptive (default) | No explicit config set | Model decides per-turn. Can consume more tokens than `low` on simple tasks. Set `thinking: low` explicitly if you want predictable token usage. |

**Rule of thumb:** Low thinking covers the vast majority of tasks. Set
`thinking: low` explicitly in your config unless you specifically want
the model to self-regulate thinking depth. Escalate to medium only when
the model must determine *what* to do (ambiguous orchestration, conflicting
data sources) — not just *how* to do it.

### Model Assignment Framework

Recommended assignments across OpenClaw contexts:

| Context | Model | Thinking | Rationale |
|---|---|---:|---|
| Conversation (main) | Daily-driver alias (`gpt54min` or `sonnet`) | Low | Best default tradeoff for normal orchestration |
| Higher-stakes decisions | Stronger alias (`gpt54`, `sonnet`, `opus`) | Low / as needed | Use when judgment quality matters more than cheap throughput |
| Research / Deep analysis | Daily driver by default, escalate selectively | Low | Only jump upward when the task actually demands it |
| Cron / Automation | Cheap but reliable alias (`gpt54min`, `haiku`, or equivalent) | Low | Spoon-fed prompts, tool discipline, predictable cost |
| Coding (opencode / ACP) | Repo-appropriate coding alias | Low | Via ACP session spawn; pick the strongest model justified by scope |

**Cron timeout constraint:** OpenClaw cron jobs have an execution timeout
(observed ~120s in practice). For complex multi-step payloads with slow tools
(e.g., feed scanners, multiple web searches), the bottleneck is tool execution
time — not model latency. Prompt optimisation (fewer steps, smarter tool order)
is a higher-leverage fix than switching models.

---

## 2.5. Security Architecture (Personal Assistant Model)

When running OpenClaw as a personal assistant — one trusted operator, loopback-only gateway, no multi-tenancy — the security model differs from multi-user deployments. The goal is to **allow full capability (read, analyze, research, messaging on request) while blocking unauthorized data exfiltration and destructive actions.**

### Threat Model

For personal assistant setups, rank threats by likelihood and impact:

| Threat | Vector | Impact | Example |
|--------|--------|--------|---------|
| **Prompt injection from web content** | `web_fetch`, `bird`, `web_search` results parsed as instructions | Credential leak, memory dump exfiltration | Attacker-controlled web page that injects SQL queries or command injection |
| **Unauthorized message exfiltration** | Compromised cron payload or prompt injection → `message` tool used to send to attacker | Data leaked to external channel | Agent sends sensitive account data or financial positions to an attacker-controlled channel |
| **Destructive exec** | `rm`, `git push`, `sudo` triggered by prompt injection or errant cron | Repo sabotage, file deletion, data loss | Injected instruction: "run: rm -rf /" or "git push" to wrong remote |
| **API overspend** | Rogue tool loops (web_fetch spam, BQ scans) | Budget burn ($50–500+) | Cron malfunction or prompt injection causes 1,000 web_fetch calls |
| **Cron exfiltration** | Compromised cron payload (human error or version control leak) | Sensitive data leaked via scheduled job | Cron sends daily financial snapshot to attacker-controlled webhook |

**Key insight:** The trusted operator (user) is the gatekeeper for legitimate actions. The security model prevents the agent from taking irreversible actions without human approval — it does NOT prevent the user from explicitly instructing the agent to do anything.

### OpenClaw Security Layers

OpenClaw provides multiple configuration points for constraint enforcement:

#### 1. Exec Approvals System

The **exec-approvals.json** file defines per-agent execution policy:

```json
{
  "version": 1,
  "defaults": {
    "security": "deny",
    "ask": "off"
  },
  "agents": {
    "main": {
      "security": "allowlist",
      "ask": "on-miss"
    },
    "cron": {
      "security": "allowlist",
      "ask": "off"
    }
  }
}
```

**Key fields:**
- `security`: `"deny"` (block), `"allowlist"` (whitelist binary paths), `"full"` (allow all)
- `ask`: `"off"` (silent), `"on-miss"` (prompt for unknown binaries), `"always"` (prompt every exec)

#### 2. Per-Agent Isolation

Cron jobs and sub-agents are isolated agents — they receive only `AGENTS.md` + `TOOLS.md`, no persona/user/memory context. Assign each cron a unique `agentId`:

```json
{
  "agentId": "cron",
  "schedule": "0 3 * * *"
}
```

This allows crons to run with a **different security policy than the main interactive session**. Example:

```json
"agents": {
  "main": {
    "security": "allowlist",
    "ask": "on-miss"
  },
  "cron": {
    "security": "allowlist",
    "ask": "off"
  }
}
```

Main agent: new binaries prompt for approval. Crons: pre-approved binaries, no prompts.

#### 3. Tool Policy (Global)

`openclaw.json` tools section controls exec behavior globally:

```json
"tools": {
  "exec": {
    "ask": "off",
    "host": "gateway",
    "security": "full"
  }
}
```

**`host: "gateway"`** routes exec through the gateway approval system (required for per-agent policy enforcement). Stricter of `tools.exec` + agent-level policy wins.

#### 4. Message / External Output Gates

Binary gate at `tools.message`:
- Allow: agent can send to configured channels
- Deny: agent cannot send (but you can manually send on-request)

No per-action approval exists yet (as of OpenClaw v2026.3.7) — it's all-or-nothing per channel. Workaround: remove the token from `~/.openclaw/.env` and manually send on request.

### Phase 1 Implementation: Gateway Routing + Cron Isolation

A working deployment combines exec-approvals with per-agent scoping:

1. **Route exec through gateway:**
   ```json
   "exec": {
     "host": "gateway",
     "security": "full",
     "ask": "off"
   }
   ```

2. **Define per-agent policy in exec-approvals.json:**
   ```json
   "agents": {
     "main": { "security": "allowlist", "ask": "on-miss" },
     "cron": { "security": "allowlist", "ask": "off" }
   }
   ```

3. **Assign all crons the same agentId ("cron") so they inherit cron-level policy.** This decouples cron execution from main interactive policy:
   ```bash
   openclaw cron edit <job-id> --set agentId=cron
   ```

**Result:** Crons run with pre-approved binary sets; main agent can prompt on unknown binaries (when ask mode is toggled). Policies are independent — change one without affecting the other.

### Phase 2: Telegram Approval Prompts

The approvals config block is available in `openclaw.json` but disabled by default
(`enabled: false`). To activate:

```json5
"approvals": {
  "exec": {
    "enabled": true,
    "mode": "session",
    "agentFilter": ["main"],
    "targets": [{ "channel": "telegram", "to": "<your-telegram-id>" }]
  }
}
```

**To enable:**
1. Set `enabled: true` in the approvals block above
2. Pre-seed binary allowlist with resolved paths (`which <binary>` on your system)
3. Toggle `ask: "on-miss"` in exec-approvals.json for the main agent

**Known limitation:** The `allow-always` persistence bug (v2026.3.7) remains —
approved binaries are not written to exec-approvals.json. Use `allow-once` for
temporary approvals and pre-seed binary allowlists manually for permanent approvals.

### Quirks & Best Practices

1. **Binary path resolution on macOS** — `/bin/date` may resolve to a different actual path at runtime. To pre-seed an allowlist, use exact resolved paths from `which <binary>` in your terminal, not assumed paths.

2. **`allow-always` approval doesn't persist (v2026.3.7 bug)** — When you approve a binary with `allow-always`, it's not written to exec-approvals.json. Workaround: pre-seed allowlist entries manually before toggling `ask: "on-miss"`. Use `allow-once` for temporary approvals.

3. **Async approval behavior** — Even with `ask: "always"`, crons do NOT block. Approval prompts return immediately; cron execution continues without waiting for your response. Plan accordingly when security matters (e.g., destructive operations should require explicit pre-approval in the cron payload, not runtime approval).

4. **`tools.exec.ask` and agent-level `ask` are evaluated independently** — Tool-level `ask` controls the strictness threshold; agent-level `security` controls the permission scope. They don't fully override each other. Stricter of both applies.

5. **Empty `defaults: {}` falls back to built-in "deny"** — Always set explicit defaults in exec-approvals.json:
   ```json
   "defaults": { "security": "deny", "ask": "off" }
   ```

6. **Unicode in cron payloads breaks silently** — Non-ASCII characters (em dashes, arrows, quotes) in JSON payloads can cause haiku to fail without error. Use `ensure_ascii=False` in Python JSON encoding; replace em dashes with `--`, arrows with `->`. Verify zero non-ASCII before deploying.

### Links

- **Exec Approvals:** https://docs.openclaw.ai/tools/exec-approvals
- **Security Model:** https://docs.openclaw.ai/gateway/security
- **Exec Tool:** https://docs.openclaw.ai/tools/exec

---

## 2.6. Multi-Agent Setup

### 2.6.1 Agent Roster

The workspace runs three distinct agents, each with its own execution policy and model:

| Agent | Role | Exec Policy | Model |
|-------|------|-------------|-------|
| `main` | Primary interactive assistant | `allowlist/on-miss` | `gpt54min` |
| `cron` | Scheduled automation | `allowlist/off` | `gpt54min` |
| `vader-yolo` | Privileged exec worker (yolo mode) | `full/off` | `gpt54min` |

> **Naming convention:** The agent names above (`main`, `cron`, `vader-yolo`) are
> illustrative. Replace `vader-yolo` with any agent ID that fits your naming convention
> (e.g., `yolo-worker`, `exec-agent`). The pattern — a privileged exec worker spawned
> by the main agent — works with any name.

**Config location:** `agents.list` in `~/.openclaw/openclaw.json`

Each agent has its own:
- `workspace` directory
- `model` assignment
- exec security tier (defined in `exec-approvals.json`)
- `subagents.allowAgents` list (controls which agents can be spawned as subagents)

### 2.6.2 exec-approvals.json — Correct Three-Agent Example

The correct three-agent exec-approvals structure:

```json
{
  "version": 1,
  "defaults": { "security": "deny", "ask": "off" },
  "agents": {
    "main":       { "security": "allowlist", "ask": "on-miss" },
    "cron":       { "security": "allowlist", "ask": "off" },
    "vader-yolo": { "security": "full",      "ask": "off" }
  }
}
```

**Tier logic:**
- `main` (`allowlist/on-miss`): Approved binaries run freely; new/unknown binaries trigger an approval prompt. Protects interactive sessions from accidental exec of unknown commands.
- `cron` (`allowlist/off`): Only pre-approved binaries execute; unknown binaries are silently denied. Crons are unattended — no prompt can be answered.
- `vader-yolo` (`full/off`): All exec is unrestricted, no approval prompts. This is intentional — vader-yolo is the designated privileged exec worker for yolo mode tasks.

> **Note:** The exec-approvals example in Section 2.5 (Security Architecture) shows both
> `main` and `cron` as `full` — that reflects a simpler single-tier setup. The three-agent
> structure above is the correct target config when vader-yolo is active.

### 2.6.3 subagents.allowAgents Config Key

The `subagents.allowAgents` key controls which agent IDs `sessions_spawn` is allowed to target from a given agent:

```json
{
  "agents": {
    "list": [
      {
        "id": "main",
        "subagents": {
          "allowAgents": ["vader-yolo"]
        }
      }
    ]
  }
}
```

- Default: only the requester can spawn itself.
- Must explicitly add `["vader-yolo"]` to main's entry.
- Without this key, `sessions_spawn(agentId: "vader-yolo")` fails silently.

### 2.6.4 Yolo Mode — UX Pattern

**Trigger:** User says "yolo mode" / "no approvals" / "go yolo"

**Worker:** `vader-yolo` agent (`exec: full/off`, typically `gpt54min`). Use a stronger override only when the task genuinely needs it.

**Pattern:**
- Main orchestrates: plans, briefs, reads back output, updates STM
- vader-yolo executes freely: no approval prompts, no read-only restriction

**Spawn pattern:**

```python
sessions_spawn(
    task="<full task brief with all context — paths, repo, goal>",
    agentId="vader-yolo",
    runtime="subagent",
    runTimeoutSeconds=300
)
```

**Critical distinctions from Mode 3 subagents:**
- Mode 3 (ad-hoc research/data) sub-agents are READ/COMPUTE ONLY — always include: `"DO NOT delete, send, modify, or take any external action. Read and report ONLY."`
- vader-yolo is a WRITE-CAPABLE worker — do NOT include the Mode 3 read-only directive. Including it defeats the purpose of yolo mode.

**Exit:** User says "exit yolo" or starts a `/new` session.

**Audit trail:** vader-yolo session logs at `~/.openclaw/agents/vader-yolo/sessions/*.jsonl`

### 2.6.5 Execution Modes Table

**First principle:** prefer built-in tools over `exec` for file reads, text edits,
HTTP fetches, searches, and similar actions that native tools already cover.
Reserve `exec` for CLIs, git, and true system commands.

All five execution modes, ranked by decision priority:

| Mode | Tool | Timeout | Use for |
|------|------|---------|---------|
| 1. Direct orchestration | Orchestrator executes directly | N/A | Tasks requiring live judgment, workspace writes, user back-and-forth |
| 2. Scheduled cron | `openclaw cron` | Per-schedule | Unattended recurring jobs (reports, monitors, health checks) |
| 3. Ad-hoc sub-agent | `sessions_spawn` (runtime: subagent) | `runTimeoutSeconds: 300` | Parallel independent research/data tasks — READ/COMPUTE ONLY |
| 4. ACP coding session | `sessions_spawn` (runtime: acp, agentId: opencode) | `runTimeoutSeconds: 300` | Delegated coding tasks via opencode-acp skill |
| 5. Yolo Agent | `sessions_spawn` (agentId: "vader-yolo", runtime: subagent) | `runTimeoutSeconds: 300` | No-approval exec — coding builds, free-form tasks when user says "yolo mode" |

**Mode 2 anti-pattern:** never combine `yieldMs` with `timeout` on long-running jobs.
A timeout kills the backgrounded process; drop `timeout` entirely when intentionally using long exec.

**Decision path (check in order):**

1. Is the user in yolo mode for this session? → **Mode 5** (until user says "exit yolo" or `/new`)
2. Is the task a recurring unattended job? → **Mode 2**
3. Are there 3+ parallel independent read/compute items? → **Mode 3**
4. Is it a non-trivial coding task? → **Mode 4**
5. Default → **Mode 1** (orchestrate directly)

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

### Payload Configuration Fields

Key fields in the `agentTurn` payload for cron jobs:

```json5
{
  "sessionTarget": "isolated",  // isolated (default), main, current, session:custom-id
  "agentId": "cron",            // routes through cron-level exec policy
  "wakeMode": "now",            // explicit; also the default
  "lightContext": true          // optional — skip workspace bootstrap file injection
                                // CLI: openclaw cron add --light-context
}
```

**`sessionTarget` values:**

| Value | Behavior |
|-------|----------|
| `"isolated"` | Fresh isolated agent context per run. Default for most crons. |
| `"main"` | Routes through main session. Avoid — causes announce fragility (see gotchas). |
| `"current"` | Binds to the session where the cron was created (resolved at creation time). |
| `"session:custom-id"` | Runs in a persistent named session that maintains context across runs. Useful for daily standups or monitors that build on previous summaries. |

**`lightContext: true`:** Skips workspace bootstrap file injection (`AGENTS.md`,
`TOOLS.md`). Use for simple data collection crons that don't need workspace context.
Reduces bootstrap overhead and speeds up isolated job startup. Omit (default false)
for crons that reference workspace file paths or need AGENTS.md rules.

### The Spoon-Feeding Pattern

```mermaid
sequenceDiagram
    participant O as Orchestrator (Main)
    participant C as Cron Agent (Isolated)
    participant T as Tools (exec/web/API)
    participant D as Delivery (Telegram)

    O->>C: Spawn with self-contained payload<br/>(AGENTS.md + TOOLS.md only)
    Note over C: No SOUL/MEMORY/USER context
    C->>C: Phase 1 — Boot (read explicit files)
    loop Phase 2 — Atomic steps
        C->>T: One tool call per step
        T-->>C: Result (or [DATA UNAVAILABLE])
    end
    C->>C: Phase 3 — Synthesize output
    C->>D: Deliver via message tool
    C-->>O: Complete (auto-announce)
```

> *(Generated via draw.io MCP Tool Server — `npx @drawio/mcp`)* [Open / edit in draw.io →](https://app.diagrams.net/?grid=0&pv=0&border=10&edit=_blank#create=%7B%22type%22%3A%22mermaid%22%2C%22compressed%22%3Atrue%2C%22data%22%3A%22jVNdb%2BIwEPw1ltIHThRa6e7RJGmFBKSCUOke3WQLlhyvL3YK3K%2B%2FXfOhEl1RJSe7XmvGM2vbw58ObAWZVptWNWIoxWh4GU61QVfaKRtoVtCnPCdttQUfWhWwpWkyV9re3YSmZ2jaoqUgNxDrydSjUQHq2%2FDyDC8RDccE9lCJ0dMO3ugvX6a38dkZn4HRH9AemKIEA%2Bw5Qq%2FRxUCMcxqpGHN95dSOVe902FLwYN4HFdpAtqGOmx0MqlqM0zfqxxMBE%2FmcL8rVj6aOhBOWXhSzUwGtOfQFLzAAL5G62K%2B48QJ592I9I9Z5Pi%2BWvylZr%2FIllVkA7EOPJr1W%2FrJVnmnveTUfiZ9D8euB8glibH8LigXB3hnqFpfetQHfF2cQ3Se2UY9NBmx0xZ0J4HwP%2Bz915VFdYZkt0JmyH2U4uOifiW7wlINrm0vwnYmG4oUUj5NMlrywXshXOZ3JySwXj1nfFtj6e%2B0b9wyvDjbQC9B%2F45F1wXVfnUN2JDrdO8o%2BtKJ%2FA96rzcV9H3sCF0dwio0zEK9HorqAA2UtdvRo7%2F4B%22%7D)

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

**The Spoon-Feeding directive structure is intentional, not boilerplate.**
Haiku and Sonnet are reliable executors of structured prompts — the heavy
`[SYSTEM_DIRECTIVE]` blocks, numbered steps, and explicit failure handling
exist because isolated cron agents have no boot context, no memory, and no
fallback. The structure does the reasoning so the model doesn't have to.
Removing guardrails from working cron prompts increases fragility; add them
only where needed, but don't strip them in the name of simplification.

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

**2026.3.11 delivery contract tightening.** Isolated crons with `delivery.mode: "none"`
can no longer rely on ad-hoc `message` tool sends to reach the user. If a job was
configured as silent-but-still-sending, it now goes silent by design. The fix is to
move the job to explicit `delivery.mode: "announce"` or `delivery.mode: "webhook"`
and keep direct `message` sends only as a deliberate in-payload fallback.

**Open issue (#43177, 2026-03-11): false-positive delivery status.** Some isolated
cron runs can be recorded as `delivered: true` / `deliveryStatus: delivered` even when
Telegram did not actually receive the message. Suspected root cause: the shared
subagent/cron announce path treats a successful internal `callGateway(... deliver: true)`
as successful external delivery without verifying the lower transport send. Treat cron
run history as advisory; if a report matters, verify against actual channel delivery or
gateway logs.

**Slow tools still dominate runtime.** In complex multi-step crons, execution
time is driven by tool calls (feed scanners can take 30–40s alone, multiple
web searches compound), not model latency. Model switches don't fix timeout
risk — prompt optimisation and step reduction do.

### Sub-agent Permission Boundary

When using `sessions_spawn` for ad-hoc sub-agents (research tasks, data
collection, parallel analysis), enforce a **READ/COMPUTE ONLY** boundary.

**The risk:** Sub-agents inherit tool access. Without explicit constraints,
a sub-agent can send emails, post to social media, delete files, or mutate
external state — all without the orchestrator's Plan & Execute approval gate.

**Rules:**

1. Every `sessions_spawn` touching write-capable tools MUST include an
   explicit constraint in the task prompt:
   `"DO NOT delete, send, modify, or take any external action. Read and report ONLY."`

2. If a task requires both read AND write: sub-agent returns results,
   orchestrator executes the write step directly (where Plan & Execute applies).

3. Write/action tasks (email sends, state changes, file deletes, outbound
   messages) MUST stay with the orchestrator — never delegated to sub-agents.

**Why this matters:** The orchestrator's approval gate (present plan → user
says "Go" → execute) is the primary safety mechanism for external actions.
Sub-agents bypass this gate entirely. The permission boundary ensures
sub-agents can't take irreversible actions without human oversight.

### Sub-Agent Decision Rules (When to Spawn vs Orchestrate)

```mermaid
flowchart TD
    Start([New task]) --> Q1{Parallel independent\nitems > 3?}
    Q1 -->|Yes| Spawn1[✅ Spawn]
    Q1 -->|No| Q2{Long compute,\nno mid-task judgment?}
    Q2 -->|Yes| Spawn2[✅ Spawn]
    Q2 -->|No| Q3{External repo,\nself-contained?}
    Q3 -->|Yes| Spawn3[✅ Spawn]
    Q3 -->|No| Q4{Touches workspace\nfiles / memory / delivery?}
    Q4 -->|Yes| Orch1[❌ Orchestrate]
    Q4 -->|No| Q5{Needs live judgment\nor user back-and-forth?}
    Q5 -->|Yes| Orch2[❌ Orchestrate]
    Q5 -->|No| Default[❌ Orchestrate\ndefault when unsure]
```

> *(Generated via draw.io MCP Tool Server — `npx @drawio/mcp`)* [Open / edit in draw.io →](https://app.diagrams.net/?grid=0&pv=0&border=10&edit=_blank#create=%7B%22type%22%3A%22mermaid%22%2C%22compressed%22%3Atrue%2C%22data%22%3A%22ldNfT8IwEADwT3OJPiyBjgZ8lA2eDErkxcfa3tika5e2c%2FrtvYIQo4VgsvTPrbn7rZdV2g6yFi4AG21KGN3TfHqeA724AT5f4UDbIPwOeHlLyyyDfEHzegzT%2BZNwQmvUtG%2BMwg5pMAF4YZqArY%2B59odzyJcw%2FV2EUhzzTYsX9DTG0p0YzJhKw4LBXQEzfgyS4FKGlT0kWDOSPVizpbW0bdcHBFZElLEUahuV7b%2BHjd56tW0jOKljZ3XsSh1L6XLSLT4COiPivTns7DfPo64yaU0QjUGVRuVnUfmVqDyFmhBqY3tZY2zaYN3Od0JiVFWN3geBLePtYWvd52mrUDfvSIEkdpLCPjpZn9pbwuwYQx%2BcoFb9FU9SYk7iFaKKtGj42U5SW0eB3mOcXoXcZcKorLIu1GkqP0dl%2F6LyBLXESvQ6XMpT0H9zOESXX6OJduN7F0t8AQ%3D%3D%22%7D)

| Signal | Decision |
|--------|----------|
| Parallel independent tasks (>3 items, no interdependency) | ✅ Spawn |
| Long compute with no mid-task judgment (deep analysis, big refactors) | ✅ Spawn |
| External / non-OpenClaw repos — self-contained, no workspace context needed | ✅ Spawn |
| Sequential task requiring live judgment calls or user back-and-forth | ❌ Orchestrate |
| Task touches workspace files, memory, or channel delivery | ❌ Orchestrate |
| Doc audits, config edits, cron changes — context IS the workspace | ❌ Orchestrate |

**Default:** When unsure → orchestrate. Sub-agent overhead (spoon-feeding context,
monitoring, output retrieval) only pays off when the task is genuinely parallel
or self-contained. For tasks that need live judgment mid-way, the orchestrator
loop with the user is faster and more accurate than a sub-agent round-trip.

---

## 4. Prompt Architecture Considerations

### Instruction Placement and Repetition

LLMs process text left-to-right with causal attention — instructions placed
before data are processed in context; instructions placed after data arrive
too late to shape how the model interpreted earlier content. This is the
"Lost in the Middle" problem.

**For OpenClaw crons, this is already solved** by the Spoon-Feeding Pattern:
`[SYSTEM_DIRECTIVE]` comes first, data collection steps follow, synthesis
comes last. Each step processes a small focused result — context never
accumulates into a monolithic block the model has to reason over in one pass.

**The "Instruction Sandwich"** (repeating key instructions at top and bottom)
is useful for single-shot prompts with 10K+ tokens of dense content between
the instruction and the question — e.g. RAG pipelines stuffing many retrieved
documents. For spoon-fed crons it adds token overhead without quality gain.
Don't sandwich working cron prompts.

**Goal-first priming** — stating the core objective before any data or tool
calls — is what `[CORE OBJECTIVE]` and `[SYSTEM_DIRECTIVE]` accomplish in
the payload skeleton. Every subsequent tool result is processed through the
lens of that objective. Putting it last (after all the data steps) degrades
adherence on longer payloads.

### Research Tool Orchestration

For research-heavy tasks (news analysis, geopolitical events, market data),
tool selection and sequencing significantly impacts output quality. The recommended
pattern is **parallel multi-source ingestion** followed by a single synthesis pass.
The orchestrating agent decides which tiers to fire and aggregates all results
into one coherent answer — the user sees only the synthesis, not the raw tool outputs.

**4-Tier research stack:**

| Tier | Tools | Mode | When to Use |
|------|-------|------|-------------|
| 1 | Brave (`web_search`) + Bird CLI + `exa.web_search_exa` + Gemini Grounding (`gemini_search.py`) | Always parallel | Every query. Brave=keyword/news, Bird=social signals, Exa=semantic/editorial diversity, Gemini=Google index+AI synthesis+full-page reads |
| 2 | `web_fetch` + `exa.crawling_exa` | Parallel, on-demand | When full article body is needed from a known URL. Both fire simultaneously. |
| 3 | Browser (`profile:openclaw` / `profile:chrome`) | On-demand, fallback from Tier 2 | JS-rendered pages, SPAs, login-gated dashboards, dynamic content. Natural escalation when Tier 2 returns empty/broken content. |
| 4 | Specialized precision tools — on-demand by query type | On-demand, not parallel by default | `exa.web_search_advanced_exa` (date/domain/category filters), `exa.company_research_exa` (company intel), `goplaces` (location lookup), `financial-datasets` (US stock/crypto), `polymarket` (prediction market odds), `serper` (raw Google SERP), `context7` (live library docs), `google-dev-knowledge` (Google developer docs) |

**Tier 1 — always parallel:**
Fire Brave + Bird + `exa.web_search_exa` + Gemini Grounding simultaneously on every
research query. No exceptions. These four tools surface different signals: Brave for
speed and news freshness, Bird for unfiltered social reactions and disinformation
detection, Exa for semantic match and non-dominant editorial angles, Gemini for
Google index + AI synthesis + full source page reads (the only Tier 1 tool that reads
full content, not just snippets).

**Gemini Grounding execution:**
- Command: `cd <path-to-gemini-search> && uv run gemini_search.py search "<query>"`
- Always use flash model (default). Pro is reserved exclusively for the Deep Analysis protocol.
- Requires `yieldMs: 30000` minimum in parallel exec blocks (API latency 15–25s). Do NOT use 25s or lower.

**Pre-flight gate (MANDATORY):** Before firing any Tier 1 research block, narrate a
visible checklist: `Tier 1: Brave ☐ / Bird ☐ / Exa ☐ / Gemini ☐` — mark each tool ☑
when included in the parallel call block. If a tool is temporarily unavailable
(rate-limited, errored), mark it ☐ with a short reason and proceed with remaining tools.
The gate blocks execution only when a tool is omitted without reason.

**Breaking event rule (MANDATORY):** For any breaking event <48h old — fire Brave +
Bird + Exa + Gemini as one parallel block, no exceptions. Breaking events are where
all four signals diverge most: Brave catches wire headlines, Bird catches unfiltered
reactions and disinformation, Exa surfaces editorial analysis from sources Brave
doesn't rank highly, Gemini synthesizes across sources with full-page reads.

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

**Pre-flight gate (MANDATORY):** Before firing any Tier 2 block on a known URL, narrate:
`Tier 2 [<url>]: web_fetch ☐ / crawling_exa ☐` — mark each tool ☑ when included.
X.com exception: skip Tier 2, Bird (Tier 1) already covers all X content.

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

**Tier 3 — browser, on-demand escalation from Tier 2:**
- `profile:openclaw`: isolated browser, no saved logins. Use for public JS-rendered
  pages where lower tiers return empty content — e.g. live trading charts, SPAs,
  public dashboards with dynamic content. Natural fallback when Tier 2 returns
  broken or empty content.
- `profile:chrome`: your active Chrome session with existing cookies. Use for
  login-gated pages. Requires the user to attach the tab via the Browser Relay
  toolbar button first.

**Tier 4 — specialized precision, on-demand by query type:**
- `exa.web_search_advanced_exa`: date filters (`startPublishedDate`), domain
  restrictions (`includeDomains`), category filters (`"news"`, `"financial report"`,
  `"research paper"`). Trigger when precision matters more than speed.
- `exa.company_research_exa`: structured company profile — headcount, funding
  history, tech stack, competitors, key executives. Trigger on explicit due diligence
  questions. NOT for breaking news about a company (Tier 1 covers that).
- `goplaces`: location and place lookup. Trigger for geographic / local business queries.
- `financial-datasets`: US stock and crypto data — income statements, filings,
  prices. Trigger for structured financial analysis. NOT for cron polling loops.
- `polymarket`: prediction market odds. Trigger when the user asks about event
  probabilities or market consensus on outcomes.
- `serper`: raw Google SERP results. Trigger when Brave coverage is insufficient
  or you need direct Google ranking signals.
- `context7`: live library and framework documentation. Trigger for API reference,
  version-specific docs, code examples.
- `google-dev-knowledge`: Google developer docs (GCP, Firebase, Android, Gemini APIs).
  Trigger for Google product integration questions.

**Decision flow:**
```
Any query →
  Pre-flight: narrate Tier 1 checklist (Brave ☐ / Bird ☐ / Exa ☐ / Gemini ☐)
  Fire Tier 1 (Brave + Bird + Exa + Gemini) in parallel

  Need full article from a URL?
  → Pre-flight: narrate Tier 2 checklist (web_fetch ☐ / crawling_exa ☐)
  → Fire Tier 2 (web_fetch + crawling_exa) in parallel
  → URL is X.com? → Skip Tier 2, Bird already covered it in Tier 1
  → Tier 2 returned empty/broken?
    → Escalate to Tier 3 (Browser)

  Content is JS-rendered or requires login?
  → Fire Tier 3 (Browser)
  → Needs session auth? → profile:chrome, user must attach tab

  Need date/domain/category precision?
  → Fire exa.web_search_advanced_exa (Tier 4)

  Need company structure/funding/headcount?
  → Fire exa.company_research_exa (Tier 4)

  Need location, financial, prediction market, raw SERP, or live docs data?
  → Fire the relevant Tier 4 specialized tool (goplaces, financial-datasets,
    polymarket, serper, context7, google-dev-knowledge)
```

**Why the orchestrator synthesizes, not the tools:**
The agent fires all relevant tiers, reads all results, and delivers one coherent
answer. This mirrors the experience of products like Google AI Mode or Exa Deep
Research, but with added context-awareness (user history, prior decisions) and
social signal integration via Bird that neither product provides natively.

### Non-Trivial Task Gate

Before starting any research, analysis, or decision task mid-session — fire
`memory_search` on the core topic first. This is a mandatory gate, not an
optional step.

**Why it matters:** An agent deep in a long session may have relevant prior
decisions, lessons, or facts in memory that aren't in the current injection
window. Proceeding without a recall step leads to repeated work, contradictory
decisions, and missed context. The cost of one `memory_search` is trivial;
the cost of a decision that contradicts a prior lesson is not.

**Rule:** One search, before acting. Applies even when the topic feels familiar
from current session context. If 0 results on first attempt, refire with
different keywords before concluding the data is missing (QMD BM25 prefers
2–4 word keyword queries — see QMD Query Strategy in Section 1).

**Scope:** Any task involving research, synthesis, investment decisions, config
changes, or anything with durable side effects. Does not apply to simple
read-only lookups or single-turn factual questions.

### llm-wiki / Preservation-First Mode

Not every research request is answer-first. Some are **preservation-first**: the user is
trying to turn a source into durable memory instead of just getting a one-shot answer.

Use llm-wiki mode when the request is effectively:
- ingest this
- harvest this
- store this properly
- make this part of memory
- preserve this source for later retrieval

Operationally, this is a different path from casual search or Light/Deep Analysis:
- casual search = answer-first
- Light / Deep Analysis = report-first
- llm-wiki = preservation-first

In live workspaces this policy typically lives in `PROTOCOLS.md` as **Research Modes &
llm-wiki Invocation Policy**. Keep the high-level distinction in the guide even if the
exact local filing rules stay instance-specific.

### Deep Analysis Protocol

For high-stakes research requiring maximum depth — investment decisions,
geopolitical assessments, architectural choices — use the **GPT sub-agent
depth + orchestrator enhancement** pattern. The sub-agent handles deep
analysis compute; the orchestrator validates, cross-references personal
context, and delivers.

**When to use:** Manual trigger only. Not for routine research.

**Architecture:**

```
Orchestrator                              GPT Sub-agent
    │                                          │
    ├── Full tiered research                   │
    │   (Tier 1 mandatory — Gemini uses Pro    │
    │    model for Deep Analysis, NOT flash;   │
    │    Brave + Bird + Exa fire as normal)    │
    │   (Tier 2 FORCED on every key source)    │
    │                                          │
    ├── Compile spoon-fed brief:               │
    │   - Tier 1+2 findings                    │
    │   - Relevant memory context              │
    │   - User's personal situation            │
    │                                          │
    ├── Spawn sub-agent ──────────────────►  Receives compiled brief
    │   model: GPT-class (via Copilot         + analysis task
    │   or equivalent frontier model)          + output path instruction
    │   runTimeoutSeconds: 300                 │
    │                                          ├── Deep analysis compute
    │                                          │
    │                                          └── Writes full output to:
    │                                              /tmp/deep-analysis-
    │                                              <label>-<YYYYMMDD>.md
    │                                          │
    ◄── Sub-agent completes ──────────────────┘
    │
    ├── Read output file directly
    │   (no byte limit — full content)
    │   Fallback: sessions_history on child key
    │
    ├── Cross-reference with personal context
    │   + verify accuracy
    │
    ├── If divergence found:
    │   → present both findings as [CONTESTED]
    │   → let user decide, do not force a verdict
    │
    ├── If convergent:
    │   → confidence goes up, label [HIGH/MEDIUM]
    │
    └── Deliver orchestrator-enhanced output
        split into ≤3,500 char chunks (1/N, 2/N)
```

> **Gemini Pro for Deep Analysis:** The Deep Analysis protocol uses Gemini Grounding with
> the Pro model (`--model gemini-3.1-pro-preview` (current as of writing — verify against latest model names)), not flash. Pro delivers deeper synthesis
> and more cited sources (15–27 vs 5–11 on flash). Pass `--model gemini-3.1-pro-preview` (current as of writing — verify against latest model names)
> explicitly. Flash remains the default for all other research. Gemini Pro is reserved
> exclusively for this protocol.

**Key implementation details:**

1. **Tier 2 checkpoint (MANDATORY before spawning):** Do NOT spawn the
   sub-agent until Tier 2 crawls are complete or explicitly timed out.
   Sub-agent synthesis built on snippets produces lower-quality output —
   the full-document crawls are what justify the depth label.

2. **Compile the brief before spawning:** Pull relevant STM context,
   project facts, applicable lessons, and Tier 1+2 research findings into
   a structured brief. Include the user's personal context where relevant.
   Pass the compiled brief as the sub-agent's full input — sub-agents are
   dumb pipes and should not need to re-derive context.

3. **Define output path before spawning:** Use
   `/tmp/deep-analysis-<label>-<YYYYMMDD>.md`. Pass the path explicitly
   in the spawn prompt: "write complete findings to that path." Vague
   language ("include", "report") causes text-only responses with no file
   written to disk.

4. **Sub-agent constraint:** Include explicitly in the spawn prompt:
   `"DO NOT delete, send, modify, or take any external action. Read and report ONLY."`

5. **Read the output file directly:** After completion, `read` the `/tmp/`
   file with no byte limit. Do not rely on the channel announce — it may
   truncate. If the file is missing (crash/timeout), fall back to
   `sessions_history` on the child session key.

6. **Never deliver raw sub-agent output.** Always orchestrator-enhanced.
   Cross-reference, verify, and layer in synthesis before delivery.

7. **Confidence tags:**
   - `[HIGH]` — orchestrator and sub-agent converge
   - `[MEDIUM]` — moderate convergence, some uncertainty
   - `[CONTESTED]` — divergence; present both findings transparently

8. **Archive if durable:** If the analysis has lasting research value,
   append key findings to `memory/YYYY-MM-DD.md`. The `/tmp/` file is
   ephemeral (cleared on restart).

9. **Message splitting:** Split final delivery into sequential messages
   ≤3,500 chars each, labeled (1/N). Never send a single synthesis block
   over the limit.

---

## 5. Coding Architecture

### Skill-First Approach

Coding tasks are delegated via the **opencode-acp skill** rather than raw command
invocations. The skill owns the HOW (ACP transport, plan file handoff, explore
workflow, completion detection, and the full Orchestrator Loop); the orchestrator
(AGENTS.md) owns the project-level constraints.

**Read the skill's SKILL.md before spawning a coding task.** It contains current
command syntax and patterns that may change with OpenClaw updates. Hardcoding
mechanics in AGENTS.md creates maintenance debt.

| Skill | Role |
|-------|------|
| `opencode-acp` | Delegates coding tasks to OpenCode via ACP (Agent Client Protocol). Handles plan file handoff, explore workflow, completion detection, and the full Orchestrator Loop. Replaces the former `opencode-wrapper` skill. |

**Preferred model:** `claude-sonnet-4-6` (Thinking: Low) via Anthropic or Google Vertex.

> **Note:** Configure the OpenCode default model in `~/.config/opencode/opencode.json`.
> Common choices include Claude Sonnet via Anthropic direct or Google Vertex ADC.
> Use the model swap script documented in the opencode-acp SKILL.md to switch models
> per-session.

**Key rules (orchestrator-level — put these in AGENTS.md, not the skill):**
- Planning stays at orchestrator level — present a plan, get approval, then delegate to skill
- `git init` always. Local commits and feature branch pushes (`git push origin feat/<slug>`) are permitted. NEVER push to `main`. NEVER merge PRs — The user merges manually.
- Local unit/functional tests with mocks. No external deps
- Project root: your preferred git directory (e.g., `~/Developer/git/`)

**Why skill-first over raw commands:**
- Skills stay up-to-date with OpenClaw releases (ACP flags, completion patterns, etc.)
- Decouples orchestrator from implementation detail
- Single source of truth for HOW; AGENTS.md only carries project constraints

### ACP Transport

OpenCode sessions are spawned via ACP (Agent Client Protocol) using `sessions_spawn`:

```python
sessions_spawn(
    task="Implement the plan at /absolute/path/.opencode/plans/plan-NNN-<slug>.md",
    runtime="acp",
    agentId="opencode",
    mode="run",
    cwd="/absolute/path/to/repo"
)
```

- `cwd` is mandatory and must be an absolute path to the repo root.
- `mode="run"` is always one-shot (completes and exits).
- `agentId="opencode"` routes the session to the opencode agent config.

**acpx backend:** acpx is the ACP execution backend bundled as an OpenClaw plugin
extension. The binary lives at the plugin path. OpenClaw upgrades wipe it — reinstall
with `cd <openclaw>/extensions/acpx && npm install` after any OpenClaw upgrade. Never
pin a specific acpx version — the extension's `package.json` declares the correct one.

### Prompt-in-File Standard

**Always write the plan to a file** before spawning — never embed long prompts inline.
Plan files live in `.opencode/plans/` inside the repo using the naming convention
`plan-NNN-<slug>.md`.

**Why this matters:** Vague language in inline prompts ("create a module",
"include tests") causes text-only responses — the agent describes what it
would do but writes no files to disk. Explicit plan files with clear directives
are reliably executed.

**Mandatory phrasing in every plan:**
- ✅ "Write the following files to the current working directory."
- ✅ "Create the following files on disk: ..."
- ❌ "Create a module" (too vague — agent may respond with text only)
- ❌ "Include tests" (too vague — may not write files)

**Plan file path:** `.opencode/plans/plan-NNN-<slug>.md` inside the target repo.

### Run Completion Detection

After spawning a coding session, check completion before reading output:

```bash
# Primary: grep gateway log for the done sentinel
grep "<SLUG>-DONE\|<uuid>" ~/.openclaw/logs/gateway.log | tail -5

# Fallback: check sessions.json for state: idle
# For explore tasks: cat <repo>/.opencode/artifacts/explore-<slug>-<date>.txt
```

Session output is available as JSONL at:
`~/.openclaw/agents/opencode/sessions/<sessionId>.jsonl`

### Orchestrator Loop

For non-trivial coding tasks, use the iterative Orchestrator Loop rather than a single
one-shot spawn:

| Step | Label | Action |
|------|-------|--------|
| 1 | `[ANALYZE]` | Spawn `@explore` sub-agent → read output from `.opencode/artifacts/explore-<slug>-<date>.txt` |
| 2 | `[PLAN]` | Present implementation blueprint to user, wait for Go |
| 3 | `[APPROVE]` | User says Go |
| 4 | `[BRIEF]` | Write `.opencode/plans/plan-NNN-<slug>.md`, spawn ACP build session |
| 5 | `[REVIEW]` | Read session JSONL, verify implementation against plan |
| 6 | `[ITERATE]` | If gaps found, write a new plan with incremented NNN and re-spawn |
| 7 | `[COMMIT]` | `git add` + `git commit` locally. The orchestrator MAY push feature branches (`git push origin feat/<slug>`) and open PRs (`gh pr create`) — but NEVER pushes to `main` and NEVER merges PRs. The user merges manually. Pre-push gate: verify remote exists (`git remote -v`) before pushing. If no remote configured → stop and ask the user to create the remote repo first. |

**Explore artifacts** go to `.opencode/artifacts/explore-<slug>-<date>.txt` inside the
repo. The `@explore` step reads source files; the orchestrator reads its output before
writing the plan.

### Vertex AI / Gemini SDK Notes (google.genai)

When building coding tools that use Google's `google.genai` SDK on Vertex AI,
watch for these non-obvious gotchas:

1. **File API is AI Studio only.** `client.files.upload()` is not supported on
   Vertex. Use `Part.from_bytes(data=pdf_bytes, mime_type=...)` for inline
   content ingestion instead.

2. **`gemini-3.1-pro-preview` requires `location="global"`** — `us-central1`
   returns 404. Confirm location in your config before running.

3. **Full model path required on Vertex:**
   `publishers/google/models/gemini-3.1-pro-preview` — not the short form.

4. **Auth:** Use Application Default Credentials (ADC) via
   `gcloud auth application-default login`. Set `GOOGLE_CLOUD_PROJECT` in
   your `.env` (git-ignored). Never hardcode credentials.

5. **Python project convention:** Use `uv init --no-workspace` + `uv add <pkg>`.
   Run via `uv run <script>.py`. Commit `.env.example` as a template;
   add `.env` to `.gitignore`.

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
mcporter --config <workspace>/config/mcporter.json list

# Inspect a server's available tools and schema
mcporter --config <workspace>/config/mcporter.json list <server-name> --schema

# Preferred call pattern: always use explicit config + JSON args
mcporter --config <workspace>/config/mcporter.json call "<server-name>.<tool-name>" --args '{"param":"value"}'
```

**Current workspace rule:** always use all 3 pieces together:
1. `--config <workspace>/config/mcporter.json`
2. quoted tool name in `"server.tool"` format
3. JSON payload via `--args '{...}'`

Avoid key=value shorthand in operational prompts — JSON `--args` is the most
reliable and matches the live workspace convention.

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
| `get_documents` | Fetch one or more full documents by name |

**Usage:**

```bash
# Search Google developer docs
mcporter --config <workspace>/config/mcporter.json call "google-dev-knowledge.search_documents" --args '{"query":"Cloud Run cold start optimization"}'

# Fetch one or more full documents (names come from search results)
mcporter --config <workspace>/config/mcporter.json call "google-dev-knowledge.get_documents" --args '{"names":["documents/docs.cloud.google.com/run/docs/configuring/healthchecks"]}'
```

### Example: Financial Data MCP Server

The [Financial Datasets MCP](https://financialdatasets.ai/) provides
structured financial data for US stocks and crypto — income statements,
balance sheets, SEC filings, earnings, and live/historical crypto prices.

**Config (`<workspace>/config/mcporter.json`):**

```json
{
  "mcpServers": {
    "financial-datasets": {
      "baseUrl": "https://mcp.financialdatasets.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_FINANCIAL_DATASETS_API_KEY"
      }
    }
  }
}
```

**Key tools (17 total in the live workspace as of 2026-03-13):**

| Tool | Description |
|------|-------------|
| `getIncomeStatement` | Annual/quarterly/TTM income statements |
| `getBalanceSheet` | Balance sheet data |
| `getCashFlowStatement` | Cash flow statements |
| `getFinancialMetrics` | P/E, EV, profitability ratios, valuation |
| `getSegmentedRevenues` | Revenue breakdown by segment/geography |
| `getNews` | Company news + press releases by ticker |
| `getFilings` / `getFilingItems` | SEC 10-K, 10-Q, 8-K full text + structured |
| `getCompanyFacts` | Market cap, employees, sector, exchange |
| `getCryptoPriceSnapshot` | Live crypto price (BTC, ETH, etc.) |
| `getCryptoPrices` | Historical crypto prices with interval |

**Usage:**

```bash
# Income statement (last 4 annual periods)
mcporter --config <workspace>/config/mcporter.json call "financial-datasets.getIncomeStatement" --args '{"ticker":"GOOGL","period":"annual","limit":4}'

# Live BTC price
mcporter --config <workspace>/config/mcporter.json call "financial-datasets.getCryptoPriceSnapshot" --args '{"ticker":"BTC-USD"}'

# Financial metrics (TTM)
mcporter --config <workspace>/config/mcporter.json call "financial-datasets.getFinancialMetrics" --args '{"ticker":"AAPL","period":"ttm","limit":1}'
```

**Note:** This is a PAYG (pay-as-you-go) API. Load credits before use.
Not recommended for cron polling loops — use on-demand for interactive
analysis sessions.

### Using MCP Tools in Agent Context

Once configured, reference MCP tools in cron payloads or interactive tasks
using the `exec` tool (mcporter is a shell CLI):

```
Step N: exec: mcporter --config /absolute/path/to/config/mcporter.json call "google-dev-knowledge.search_documents" --args '{"query":"your query here"}'
```

**Spoon-feeding rules still apply:**
- One `mcporter call` per numbered step
- Use `--output json` for structured results the agent can parse
- Hardcode the full `mcporter call` command with absolute config path if running
  from a cron (isolated agent has no working directory):

```
exec: mcporter --config /absolute/path/to/config/mcporter.json call "server.tool" --args '{"key":"value"}'
```

### MCP in TOOLS.md

Document active MCP servers in `TOOLS.md` so agents can reference them:

```markdown
## MCP Tools (mcporter)
- Config: `<workspace>/config/mcporter.json`
- Active Servers:
  - `google-dev-knowledge` — Google Developer docs (GCP, Firebase, Gemini APIs, etc.)
    Tools: search_documents, get_documents
    Usage: `mcporter --config <workspace>/config/mcporter.json call "google-dev-knowledge.search_documents" --args '{"query":"..."}'`
```

---

## 7. Operational Procedures

### Maintenance Cron Pattern

Intelligence crons (news, market data, social signals) collect and deliver
information. **Maintenance crons** are a distinct category — they run system
health checks and upkeep tasks on a schedule. Both follow the same
Spoon-Feeding Pattern, but maintenance crons report on the system itself.

**Reference implementation: `proc-janitor-nightly`**

A nightly maintenance cron typically covers 4 sections:

```
Section A — Process cleanup
  Run the process janitor tool.
  Report full output verbatim (no summarization).

Section B — Memory backend health
  Check the memory backend status (e.g., openclaw memory status --json).
  Flag: provider not "qmd" (fallback active), dirty=true (index stale),
        files=0 (nothing indexed), command failure.

Section C — Token/usage analytics
  Run token usage analytics script.
  Report last N days verbatim — every line, no collapsing.

Section D — Bootstrap injection sizes
  Run workspace size check script.
  Flag any file at ≥80% of the per-file injection cap (20,000 chars).

Section E — Post-prework context estimate
  Report estimated context window usage after a typical prework boot.
  Flag at ≥20% of the full context window.
```

**Why separate sections matter:** A maintenance cron isn't just cleanup —
it's a health dashboard. Sections D and E give early warning before injection
truncation or context bloat degrades session quality. Without them, files can
silently exceed the bootstrap cap and the agent loses access to critical
lessons without any error.

**Scheduling:** Run nightly during low-traffic hours (e.g., 03:00 local time).
No conflicts with intelligence crons if scheduled at a different hour.

**Key payload rules (same as intelligence crons):**
- `[CRITICAL - DELIVERY]` required — maintenance reports are long; announce
  delivery fails silently for large outputs (see Section 3 gotcha)
- `model: low-cost reliable alias`, `thinking: low` — `gpt54min` is a strong default; `haiku` is fine for Claude-centered setups
- `wakeMode: "now"` (explicit; this is also the default when omitted)
- Do NOT add `--dry-run` to the process janitor step — the cron exists to
  actually run the cleanup, not preview it

**Workspace size check script pattern:**

```python
# workspace_size_check.py — minimal reference pattern
# Section D: per-file bootstrap injection sizes
BOOTSTRAP_FILES = [
    "AGENTS.md", "MEMORY.md", "TOOLS.md", "SOUL.md",
    "HEARTBEAT.md", "IDENTITY.md", "USER.md"
]
PER_FILE_CAP = 20_000   # chars (bootstrapMaxChars)
TOTAL_CAP = 150_000     # chars (bootstrapTotalMaxChars)

# Section E: post-prework context estimate
# Estimate: bootstrap + STM + projects.md + recent dated memory + N SKILL.md files
# Compare against the model's context window (e.g., 200k tokens)
# Warn at ≥20% (40k tok), flag red at ≥30% (60k tok)
```

Adapt thresholds to your workspace's actual injection habits.

---

### Operational Rituals

These named rituals standardize recurring maintenance patterns. Define trigger
words in `AGENTS.md` so the agent executes the correct sequence when invoked.

#### Prework

**Trigger word:** "prework"

A readiness sequence to run before starting a non-trivial task — particularly
at the start of a new session or after a long break. Ensures the agent has
current context before acting.

**Steps:**
1. **Re-execute SESSION START** — Re-read the boot sequence files exactly as
   defined in `AGENTS.md`. No shortcuts. Confirm understanding.
2. **Skill scan (lazy)** — Do NOT preload baseline SKILL.md files at prework.
   Skills are loaded on-demand when a task triggers them (per the skill scan rule
   in the system prompt). Exception: if STM identifies a specific skill as actively
   in-progress for the session, read that one SKILL.md only.
3. **Protocol awareness** — Note that `PROTOCOLS.md` (workspace root) contains
   full procedure details for triggered protocols such as Distill & Flush,
   Spa Day, Research Modes / llm-wiki routing, and the Coding Task Protocol.
   Deep Analysis often lives in a dedicated skill instead of `PROTOCOLS.md`.
   These are referenced from `AGENTS.md` but only read when explicitly triggered by name.
4. **Confirm back to user** — Report: (a) which memory files were read and any
   relevant lessons surfaced, (b) which SKILL.md files were loaded with key
   gotchas per skill, (c) restate the Research and Memory retrieval rules in
   your own words as confirmation.

The confirmation step is mandatory — it proves prework was completed, not
skipped. An agent that reads the files but skips confirmation may still proceed
from stale assumptions.

#### Spa Day (Context Optimization)

**Trigger word:** "spa day" or "context optimization"

A periodic context hygiene pass — more aggressive than Distill & Flush. Run
when sessions feel sluggish, boot context is growing, or MEMORY.md is
approaching the injection limit.

**Steps:**
1. Compress verbose MEMORY.md entries to 1–2 lines each
2. Archive time-bound content to `memory/YYYY-MM-DD-memory-archive.md`
3. Check cross-file duplication — remove any entry that already appears
   in another file
4. Audit MEMORY.md Lessons Learned and Decisions Log — remove any entry
   that has been codified into `AGENTS.md`, `TOOLS.md`, or any active
   `SKILL.md`. MEMORY.md should only hold what isn't captured elsewhere.
5. Run workspace size check script to verify file sizes and headroom
6. Run `openclaw sessions cleanup --enforce`

**Target:** MEMORY.md < 15KB, zero truncation, no duplication.

**Frequency:** Monthly, or when the nightly maintenance cron flags Section D
or E warnings.

---

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
[ ] Model set to an appropriate low-cost alias with low thinking (`gpt54min` preferred; `haiku` acceptable for Claude-centric setups)
[ ] Schedules staggered ≥15min apart from other crons delivering to the same channel
[ ] agentId NOT set to "main" (use default agent for isolated crons)
[ ] wakeMode set to "now" (default, but explicit is cleaner — avoids ambiguity when cloning/migrating crons)
```

### Verification Checklist (after workspace changes)

```
[ ] AGENTS.md boot steps point to valid files
[ ] AGENTS.md model assignments reflect current active models
[ ] SOUL.md references to AGENTS.md match actual section headers
[ ] SOUL.md Distill & Flush targets exist (MEMORY.md, memory/projects.md)
[ ] MEMORY.md decisions log updated with any architectural changes
[ ] MEMORY.md size < 15KB (check with wc -c; prevent injection truncation)
[ ] memory/projects.md backlog is current
[ ] Cron job absolute paths match actual file locations
[ ] Cron job model assignments match AGENTS.md model section
[ ] Active skill roster reflects current active/disabled skills
[ ] QMD binary accessible (if enabled): run memory_search and confirm provider: "qmd"
[ ] MCP server configs in mcporter.json verified with mcporter list
[ ] Session reset config at top level of openclaw.json (not agents.defaults)
[ ] Total boot context < 60KB (measure with wc -c on all workspace files)
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
| Financial Datasets MCP | https://financialdatasets.ai/ |
| ClawHub (Skills Registry) | https://clawhub.com |

---

## 9. Revision History

| Date | Change |
|------|--------|
| 2026-04-06 (v15) | Provider-agnostic refresh. Title/intro de-Anthropicized while keeping the historical filename, model strategy rewritten around stable aliases and multi-provider routing, execution modes updated with the built-in-tools-first rule and the Mode 2 `yieldMs` + `timeout` anti-pattern. Companion `WORKSPACE_REFERENCE.md` refreshed first so the public guide continues to stay generic while the personal overlay carries instance-specific truth. Later same day: guide-sync audit re-run against a fresh dated artifact (`explore-guide-sync-20260406.txt`) corrected stale Sonnet/Haiku-era leftovers, fixed skills precedence order, updated PROTOCOLS/llm-wiki wording, expanded alias examples, corrected multi-agent model rows, and refreshed cron-model wording. |
| 2026-03-31 (v14.2) | Multi-agent setup + yolo mode (NEW Section 2.6): vader-yolo agent architecture, exec security tiers (main=allowlist/on-miss, cron=allowlist/off, vader-yolo=full/off), subagents.allowAgents config key, yolo mode UX pattern (trigger/worker/exit/audit trail), Mode 5 added to execution modes table. Priority 2 fixes: QMD includeDefaultMemory=false, prework skill scan lazy pattern, pre-flight gate narration added to Tier 1+2 research, [COMMIT] step updated with branch push policy, opus-av alias added, skills precedence tiers corrected to 6 levels. v14.1: scrubbed personal references (personal names → user), generalized model aliases to representative examples by provider category, removed instance-specific config notes, generalized agent naming. v14.2: generalized ~/gemini-search and ~/clawd paths to placeholders, added model ID age qualifier, clarified revision history reversion notes, added exec-approvals section comment. |
| 2026-03-21 (v13) | **Full alignment refresh vs live workspace (2026-03-21) + official docs audit.** Research Protocol: Gemini Grounding promoted to mandatory Tier 1 (4th tool); pre-flight gate narration rule added for both Tier 1 and Tier 2; Tier 3/4 renumbered (Browser→T3, Specialized precision tools→T4, with 6 new domain-specific tools documented); breaking event rule updated to include Gemini. Coding Architecture: `opencode-wrapper` replaced by `opencode-acp` skill; ACP transport (`sessions_spawn(runtime="acp")`) replaces PTY/tmux; plan files in `.opencode/plans/plan-NNN-<slug>.md`; explore artifacts in `.opencode/artifacts/`; completion via gateway log grep; acpx backend concept added; Orchestrator Loop steps added with ACP-era labels. Memory tiers: L2 = full `memory/` folder (projects + dated files, organizational not tier boundary); L3 = MEMORY.md (auto-injected); `memory_search` reframed as retrieval mechanism, not a tier. Model aliases: config structure updated to `agents.defaults.models[id].alias`; 7 new aliases added (opus, gpt54min, grok, kimi, minimax, deepseek, qwen-local); Opus row added to assignment table. Medium additions: PROTOCOLS.md triggered procedure store documented; Deep Analysis Gemini Pro distinction noted (Pro for DA, flash for all other research) + gpt54 sub-agent model updated; `memory_get` tool documented alongside `memory_search`; `lightContext` + `sessionTarget` current/session:custom-id added to cron payload fields; approvals block updated from future to configurable (enabled: false); ClawHub registry added. Prework ritual updated to 4 steps (protocol awareness added as step 3). Draw.io edit links removed from diagrams with content changes. |
| 2026-03-13 (v12) | **Alignment refresh vs live workspace:** corrected model policy drift (interactive default back to sonnet low; gpt54 overflow; haiku cron-only), updated `gpt54` alias to `github-copilot/gpt-5.4`, replaced stale QMD source-build instructions with live bun package + `better-sqlite3` rebuild flow, updated mcporter examples to the current `--config ... call "server.tool" --args ...` pattern, corrected Google Developer Knowledge tool names (`search_documents`, `get_documents`), updated Financial Datasets count to 17, and documented the 2026.3.11 isolated-cron delivery contract tightening plus issue #43177 false-positive delivery status bug. |
| 2026-03-08 (v11) | **Section 2.5 (NEW):** Added Security Architecture subsection — comprehensive guide to threat model (prompt injection, exfiltration, destructive exec, API overspend), OpenClaw security layers (exec-approvals.json, per-agent isolation, tool policy, message gates), Phase 1 implementation (gateway routing + cron isolation with config example), Phase 2 future state (Telegram approval prompts), and 6 quirks/best practices (binary path resolution, allow-always bug, async approvals, independent eval of ask/security, empty defaults, unicode in crons). Threat model table ranks by likelihood + impact. Config examples are generic (no personal paths/credentials). Links to official exec-approvals, security model, and exec tool docs. |
| 2026-03-08 (v10) | **Section 2 model table:** Updated interactive/conversation thinking from `Low` → `Medium` (haiku thinking:medium is the correct interactive default; crons stay at low). (reverted in v12) Added `sonnet-gh` alias (`github-copilot/claude-sonnet-4.6`, 125k ctx) to Model Aliases section with usage note. **Section 1 context optimization:** Added `memoryFlush.softThresholdTokens` config recommendation (15,000) with rationale — single large tool response can skip a 4k flush window entirely. **Section 3:** Added Maintenance Cron Pattern subsection — documents the 4-section health report structure (process cleanup, memory backend, token analytics, workspace size), workspace size check script pattern, scheduling guidance, and key payload rules. **Section 4:** Added Non-Trivial Task Gate — mandatory `memory_search` before any research/decision task mid-session. **Section 7:** Added Operational Rituals subsection documenting Prework (3-step: re-boot → skill scan → confirm) and Spa Day / Context Optimization (6-step compaction with MEMORY.md audit). **Section 7 checklist:** Added `wakeMode: "now"` to Cron Creation Checklist (item 13) — prevents scheduler drift; "timezone" property causes drift in Beta. |
| 2026-03-08 (v9) | **Section 1 alignment audit vs official docs:** Added `BOOT.md` entry (gateway-restart checklist, distinct from `HEARTBEAT.md`). Added `BOOTSTRAP.md` to formal file map. Added Workspace Directories section (`skills/`, `canvas/`, `memory/`). Fixed `TOOLS.md` description — added "does not control tool availability" per official docs. Fixed `HEARTBEAT.md` description — added "keep short, token burn risk" per official docs. Fixed injection limit — "~18KB" replaced with official `bootstrapMaxChars: 20,000 chars` + `bootstrapTotalMaxChars: 150,000 chars`. |
| 2026-03-07 (v8) | **Model policy update:** Interactive default switched from `claude-sonnet-4-6` → `claude-haiku-4-5` (sonnet quota burn at 31%/24h unsustainable) (reverted in v12). Sonnet now explicit-invocation only: deep analysis, high-stakes decisions, complex multi-source synthesis. Updated model table, AGENTS.md, MEMORY.md, TOOLS.md, openclaw.json accordingly. GPT-5-mini documented as zero-quota throwaway option. |
| 2026-03-07 (v7) | **draw.io + Mermaid diagrams:** Added 4 Mermaid diagrams to guide (workspace file injection, memory tiers, cron execution sequence, sub-agent decision flowchart). Each diagram has draw.io MCP Tool Server edit link below it. CODE_STANDARDS.md expanded with diagram type guide and examples. |
| 2026-03-07 (v6) | **Housekeeping / alignment:** MEMORY.md aligned to AGENTS.md as source of truth — removed conflicting model decision entry (haiku for standard sessions, contradicted AGENTS.md sonnet policy), added sub-agent decision rules to Decisions Log. TOOLS.md updated: removed temp haiku note, confirmed sonnet as default model. openclaw.json `agents.defaults.model.primary` updated to `anthropic/claude-sonnet-4-6`. No architectural changes — guide content was already accurate. |
| 2026-03-07 (v5) | **Section 1:** Added QMD search mode note — `search` (BM25) is the correct mode; `vsearch` and `query` are unreliable on memory-constrained hardware. **Section 2:** Added Model Providers subsection documenting three provider paths (Anthropic direct, Vertex ADC, GitHub Copilot) with auth methods and use cases. Added Model Aliases subsection — `openclaw.json` alias config pattern with examples; enables provider switching without updating cron prompts. **Section 4:** Replaced Tenth Man skeptical sub-agent pattern with redesigned Deep Analysis Protocol — GPT sub-agent writes full output to `/tmp/deep-analysis-<label>-<YYYYMMDD>.md`; orchestrator reads file directly (no truncation); fallback to `sessions_history`; divergence → `[CONTESTED]` (both findings shown, user decides); convergence → `[HIGH/MEDIUM]`; `runTimeoutSeconds: 300`; mandatory output file path + "write to disk" instruction in prompt; never deliver raw sub-agent output. **Section 5:** Added opencode-wrapper skill alongside coding-agent skill — two-skill architecture documented. Added Prompt-in-File Standard subsection — always write prompt to file, never inline in bash; mandatory "write these files to the current working directory" phrasing; vague language causes text-only responses. Added Run Completion Detection subsection — tmux session check as primary, ps fallback, run-manifest.json for provenance. Added Vertex AI / Gemini SDK Notes subsection — File API AI Studio only (use Part.from_bytes on Vertex), location=global requirement, full model path format, ADC auth, uv project convention. |
| 2026-03-04 (v4) | **Section 1:** Added QMD Query Strategy subsection — BM25 prefers 2–4 word keyword queries; verbose queries fail silently; workaround is atomic search splits; critical for haiku/sonnet-class models. Added Context Optimization & Memory Compaction subsection — archive convention (`memory/YYYY-MM-DD-memory-archive.md`), boot context targets (<60KB total, <15KB MEMORY.md), Distill & Flush compaction workflow, truncation risk documentation. Added Session Reset Configuration subsection — config at top level (not `agents.defaults`), `daily` vs `idle` modes, model override scoping (session-scoped only). Updated boot pattern from "scan last 7 days" to "read today's + yesterday's" (more precise). Added archive files to Content Taxonomy. **Section 2:** Added Adaptive Thinking note (default in OpenClaw for Claude 4.6; explicit `thinking: low` overrides). Updated Thinking Budget table with Adaptive row. **Section 3:** Added Sub-agent Permission Boundary subsection — READ/COMPUTE ONLY for ad-hoc sub-agents, orchestrator retains write actions, explicit constraint wording. **Section 4:** Added Deep Analysis Protocol (Tenth Man Pattern) — skeptical sub-agent architecture for high-stakes research, Tier 2 checkpoint, spoon-fed prompts, confidence tagging, message splitting. **Section 6:** Added Financial Datasets MCP as second example server (13 tools, PAYG billing, usage patterns). **Section 7:** Updated Verification Checklist with MEMORY.md size check, session reset config location, total boot context measurement. **Section 8:** Added Financial Datasets MCP link. |
| 2026-03-02 (v3.1) | Section 1 (QMD): Added health check note — `openclaw memory status` is the correct command; `qmd status` checks a separate CLI database unrelated to the OpenClaw-managed instance. Key fields: `provider: "qmd"`, `dirty: false`, `files > 0`. |
| 2026-03-01 (v3) | Section 1: Added STM-as-sole-task-source-of-truth rule (dated files are reference/intel only, not task queues). Clarified Content Taxonomy: time-bound intel/research outputs route to `memory/YYYY-MM-DD.md`, not `MEMORY.md`. Section 4: Added Breaking Event Rule (mandatory Brave+Bird+Exa triple parallel for events <48h old). Added Anchor+Angle query pattern (never two near-identical parallel queries). Added Proactive Content-Type Tier 2 trigger (fire `crawling_exa` on institutional/paywalled sources without waiting for a known URL). Added Deep Research Mode (3+ research turns → default every institutional source to Tier 2 crawl). |
| 2026-03-01 (v2) | Section 4: Full rewrite of Research Tool Orchestration — upgraded to complete 4-tier architecture. Tier 1: Brave+Bird+Exa search always parallel. Tier 2: web_fetch+crawling_exa parallel URL extraction with X.com exception documented (both tools blocked on x.com, Bird is correct tool). Tier 3: web_search_advanced_exa (precision filters) + company_research_exa (structured company intel) on-demand. Tier 4: Browser with two profiles — profile:openclaw (public JS pages) vs profile:chrome (login-gated, requires Browser Relay attach). Added decision flow pseudocode and orchestrator synthesis rationale. |
| 2026-03-01 | Section 2: Removed Opus from model strategy — Sonnet is now the default for all roles including research and deep analysis. Simplified Thinking Budget table (removed High tier). Updated Model Assignment Framework table accordingly. Section 1: Updated On-Demand Files boot pattern — replaced hardcoded `YYYY-MM-DD.md` with resilient "scan last 7 days" approach. Section 4: Added Research Tool Orchestration subsection — documents Brave+Bird parallel (Tier 1), Exa for breaking events (Tier 2), web_fetch for verification (Tier 3), Browser for interactive (Tier 4); includes breaking events parallel execution rule and rationale for each tier's placement. |
| 2026-02-27 | Section 3: Added `[CRITICAL - DELIVERY]` block to Payload Skeleton and `[TOOLS]` section. Added new Common Gotcha: announce delivery silently fails for large outputs (v2026.2.25 regression) — `message` tool is the reliable fix, `delivery.mode: announce` retained as fallback. Updated `[CRITICAL]` description to document labeled blocks pattern. Added `[CRITICAL - DELIVERY]` to Cron Job Creation Checklist. |
| 2026-02-25 | Instance-specific config notes added (no generic pattern changes). Section 5: added instance note block — Anthropic direct OAuth broken, working path is Google Vertex ADC (`google-vertex-anthropic/claude-sonnet-4-6@default`, `us-east5`). Section 2 model table: linked coding row to Section 5 note. TOOLS.md addition: Gemini CLI section added as a headless analytics proxy layer (taxonomy-correct, no guide changes needed). Confirmed all 7 workspace files aligned to guide taxonomy after audit. |
| 2026-02-23 | Added QMD memory backend subsection (Section 1): install pattern, config, memory pressure notes, updated L3 tier diagram. Updated model assignment table: haiku confirmed for crons (resolved backlog item). Added two cron gotchas: same-minute scheduling race condition and `agentId: "main"` fragility. Added parallel cron support note (v2026.2.22). Added new Section 6: MCP Tools Integration via mcporter — config pattern, core commands, HTTP/stdio server examples, google-dev-knowledge reference, agent usage pattern. Updated operational checklists. Added QMD + mcporter reference links. Renumbered sections 6→7 (Operational), 7→8 (Reference Links), 8→9 (Revision History). |
| 2026-02-20 | Skill-first coding: Section 5 updated to delegate via coding-agent skill instead of raw opencode command. Added CLI startup warning pattern to Section 3 gotchas and Section 6 checklist. |
| 2026-02-19 | Initial creation. Forked from `openclaw-gemini-guide.md`. Replaced Gemini model strategy with Anthropic. Updated model assignments, coding architecture, and cron notes to reflect Claude Max migration. |
