# OpenClaw + Anthropic: Workspace & Prompt Architecture Guide

> Practical patterns for running OpenClaw with Anthropic Claude models (Claude Max plan).
>
> **OpenClaw docs:** https://docs.openclaw.ai/
> **Last updated:** 2026-03-13 (v12)

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
| `skills/` | Workspace-specific skills | Overrides managed/bundled skills when names collide. Takes priority over `~/.openclaw/skills/`. |
| `canvas/` | Canvas UI files for node displays | e.g. `canvas/index.html`. Optional. |
| `memory/` | All dated logs, project context, archives | Indexed by QMD. Not injected automatically — read via boot sequence or `memory_search`. |

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
| `memory/*.md` (recent, last 48h) | Recent session context | Boot step: read today's + yesterday's dated file | L3 |
| `memory/*.md` (older) | Historical journal archive | `memory_search` | L3 |

> **Boot pattern (2026-03-04):** Read today's and yesterday's main dated files
> (`memory/YYYY-MM-DD.md`) if they exist. If none within 48h, read the single
> most recent one. Sub-files (e.g. `2026-03-02-session-name.md`) are auto-generated
> session transcripts — skip at boot, available via `memory_search` if needed.

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
        DATED["memory/YYYY-MM-DD.md\nL3 Recent dated files"]
    end

    subgraph OnDemand["On-demand via memory_search"]
        SEARCH["memory/*.md\nHistorical archive"]
    end

    Main["Main Agent"] --> Auto
    Main --> Boot
    Main --> OnDemand

    Cron["Cron / Sub-agent\n(isolated)"] --> AGENTS
    Cron --> TOOLS
```

> *(Generated via draw.io MCP Tool Server — `npx @drawio/mcp`)* [Open / edit in draw.io →](https://app.diagrams.net/?grid=0&pv=0&border=10&edit=_blank#create=%7B%22type%22%3A%22mermaid%22%2C%22compressed%22%3Atrue%2C%22data%22%3A%22jZRhb5swEIZ%2FDVI7iYlS5QeQQJtMoVSEfOinyTHXxCvYmW2i9t%2FPZxsypdlchMQZHw%2Fv3b2wl%2BR4iNJkXUdJZq7TqYbd3u9lgxbRbB6lKUYx47%2BAamjNDpxAfpirHiQ329Esv6D8fWaPxVOz8SAbf%2B%2FbaLbgz1JoQUWnbJ7ZTnZCaNQAvwfgFILoTbVdOzBGIxakEpxMUC14mLTKjbBV8%2BJo48oTn0gPE06KLozbboraoTDymK0CafaOUryyLzCaqlr7ttnQU1b8VZ6LA66Z%2FrAFqCBxWWR1My%2ByxlGnpScvgXQaB08PQN%2BCtLIoq9o3zMWesxgkcT7pBN%2FHGmRv4h56gaa5QgXe4p1%2FGnGOtrDvqYEgl%2BizWW7g%2FdgxyvRt2C5N6TDqIKS2wmInyytf36FfqWYnnLcm6i3c1Oe6%2BuGoY4UPZsL4qaiRmmKau4fdFVzDuw6C86wp8gvyiznisozzfGTfm8waqPGBCVrfd%2FTXdeWhVlc8h56YJPveisetW6bJiZFpij8VEEkP4YYbhy2WFzV8G%2B3GlBaSUdLhRA3Odv2rmkvCuPceRmZse9sD%2B3yaxHF0X0T%2BH3blyXOGNdd%2FM6aefBKxkMKLsBHee8Cyh11MrBxT5g1TosO53H4W5%2F6MV5jnHPvp%2FwE%3D%22%7D)

> **Key rule:** Cron and sub-agents only receive `AGENTS.md` + `TOOLS.md`.
> All other context must be spoon-fed explicitly in the cron payload.

### Content Taxonomy

| Content Type | Belongs In | NOT In |
|---|---|---|
| Operational protocols, rules, boot sequence | `AGENTS.md` | ~~MEMORY.md~~ |
| Curated facts, decisions, lessons learned (durable, timeless) | `MEMORY.md` | ~~AGENTS.md~~ |
| Time-bound intel, research outputs, event records | `memory/YYYY-MM-DD.md` | ~~MEMORY.md~~ |
| Archived detail from context optimization | `memory/YYYY-MM-DD-memory-archive.md` | ~~MEMORY.md~~ |
| Persona, tone, vibe, journaling protocol | `SOUL.md` | |
| Identity card (name, creature, emoji) | `IDENTITY.md` | |
| User profile | `USER.md` | |
| Infrastructure (IPs, entities, paths) | `TOOLS.md` | |
| Health check protocol | `HEARTBEAT.md` | |
| Active project state | `memory/projects.md` | |
| Transactional task tracking | `short-term-memory.md` | |
| Recent session context | `memory/*.md` (last 48h) | |

### Memory Tier Architecture

```mermaid
graph TD
    Boot["Session Boot"] --> L1["L1 — STM\nshort-term-memory.md\nActive tasks · read at boot"]
    Boot --> L2["L2 — Projects\nmemory/projects.md\nProject context · read at boot"]
    Boot --> L3["L3 — Search\nmemory_search\nSearches memory/*.md + MEMORY.md"]

    L3 --> QMD["QMD backend\nBM25 + vectors + reranker\n(optional, experimental)"]
    L3 --> SQLite["Built-in SQLite\n(default)"]

    style L1 fill:#d4edda,stroke:#28a745
    style L2 fill:#d1ecf1,stroke:#17a2b8
    style L3 fill:#fff3cd,stroke:#ffc107
    style QMD fill:#f8f9fa,stroke:#6c757d
    style SQLite fill:#f8f9fa,stroke:#6c757d
```

> *(Generated via draw.io MCP Tool Server — `npx @drawio/mcp`)* [Open / edit in draw.io →](https://app.diagrams.net/?grid=0&pv=0&border=10&edit=_blank#create=%7B%22type%22%3A%22mermaid%22%2C%22compressed%22%3Atrue%2C%22data%22%3A%22pZJvb4IwEMY%2FTZO5hAWKDH0p6l5JNufe7NVSy3Uy%2FpS01ei332ERhUiyZAnJtU%2Bvz%2F3uyrdi1Y5Q92NB3BnG9oukNCSICKUb0DqV5UWjlAQL3DgO8ZcYV55Nw4gXl5RMXDId43rzEZNgXuqdVMYxoAqngEKq01OR1PqMm%2FQAmGeYznR9d05JFOJCAUswMKzlbq8l7%2FDdUNCGgvYo3pT8AW50XdLWJ%2FSlasQGpcnBbC5LA0fzbxq%2FofH7MwGm%2BO7K8qVbwR5BPYmW87EGrAugmRsv49f3z7NyIehCnKtdENbxwjLUCyRnPIPy3G0U06A1PWDfUul2r0CxMgNVJz7IyuDDs5zQOR7BsQKVFlAalo%2FuTqEDsFmvUgOWIdqnuXHS8kZG%2BwQE2%2BdmNNSPNqcc7B9GXZHmOfHx3E%2FGkCQMmbRRMgMr0gkLx8GQAe0aeMCF1zPwQka3kyEDv2MghPB50jMQgntuOGBgH%2BHGYSKmot%2FDMw%2BDMBlwaOb2R5Nf%22%7D)

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

## 2. Anthropic Model Strategy

### Model Providers

OpenClaw supports multiple model providers simultaneously. For Anthropic-first
deployments, three provider paths are available:

| Provider | Auth Method | Best For |
|----------|-------------|----------|
| Anthropic direct | OAuth / API key | Primary — full model access |
| Google Vertex ADC | Application Default Credentials | Fallback when Anthropic OAuth is broken; Claude models via Vertex |
| **GitHub Copilot** | `openclaw models auth login-github-copilot` | Hybrid supplement — GPT-5.x, Grok, Gemini via Copilot subscription |

**GitHub Copilot as an OpenClaw provider** is useful when you want access to
non-Anthropic frontier models (GPT-5.2, GPT-5-mini, Grok, Gemini Pro) within
the same agent context, without managing separate API keys. Auth via GitHub
OAuth; models appear in `openclaw models list --all` once configured.

Copilot includes 1,500 premium requests/month with overage pricing beyond that.
Check current model availability with `openclaw models list --all` — models
showing `configured,missing` are not yet in the Copilot API catalog.

### Model Aliases

OpenClaw supports user-defined model aliases in `~/.openclaw/openclaw.json`.
Aliases let you switch providers without updating every cron prompt or config
reference — just update the alias target.

```json5
"models": {
  "aliases": {
    "sonnet": "anthropic/claude-sonnet-4-6",
    "sonnet-gh": "github-copilot/claude-sonnet-4.6",
    "haiku": "anthropic/claude-haiku-4-5",
    "gpt54": "github-copilot/gpt-5.4",
    "gpt5min": "github-copilot/gpt-5-mini",
    "gemini-pro": "google/gemini-3.1-pro-preview",
    "gemini-flash": "google/gemini-3-flash-preview"
  }
}
```

> **`sonnet-gh`** maps to `github-copilot/claude-sonnet-4.6` — the Copilot-routed
> Sonnet variant (125k context). Useful when you want Sonnet without consuming
> Anthropic direct quota. Route OpenClaw config/optimization tasks through this
> alias on fresh sessions to preserve Claude Max headroom.

Use aliases in cron payloads, `sessions_spawn`, and `/model` overrides.
When a provider rotates model names (common with Copilot as new releases land),
you update one alias and all references inherit the change.

### Model Comparison

| Aspect | Haiku | Sonnet | Opus |
|--------|-------|--------|------|
| Latency | Very low (~1-3s) | Low-Medium (~3-8s) | Higher |
| Cost / quota pressure | Lowest | Balanced default | Highest |
| Instruction-following | Good on spoon-fed tasks | Excellent | Excellent |
| Reasoning depth | Adequate for structured cron work | Strong default for conversation, research, and orchestration | Highest ceiling on subtle judgment and deep multi-hop reasoning |
| Best for | Cron jobs, schema-rigid short tasks | Interactive default, research, analysis, synthesis, coding orchestration | Explicit escalation when Sonnet is capped or the task genuinely benefits from frontier depth |

**Current workspace policy (2026-03-13):** Sonnet is the interactive default at
**thinking: low**. Haiku is reserved for cron/intelligence protocols. GPT-5.4
is the overflow path when Sonnet quota is capped. Opus is optional, manual, and
best reserved for hard depth-first work where its larger output ceiling or
reasoning robustness materially changes the result.

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
|---------|-------|----------|-----------|
| Conversation (main) | `claude-sonnet-4-6` | Low | Interactive default — best reliability/quality tradeoff for research, orchestration, and synthesis |
| Weekly quota overflow | `github-copilot/gpt-5.4` | Low / default | Use when Sonnet quota is capped and you still need strong general performance |
| Research / Deep analysis | `claude-sonnet-4-6` | Low | Default path unless the task explicitly justifies Opus or a dedicated Deep Analysis protocol spawn |
| Cron / Automation | `claude-haiku-4-5` | Low | Spoon-fed prompts handle complexity; low thinking is fastest and reduces timeout risk on bounded tasks |
| Coding (opencode) | `claude-sonnet-4-6` | Low | Via `opencode run -m anthropic/claude-sonnet-4-6` (see instance note in Section 5) |

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
| **Unauthorized message exfiltration** | Compromised cron payload or prompt injection → `message` tool used to send to attacker | Data leaked to external channel | Agent sends BTC position or financial data to attacker-owned Telegram account |
| **Destructive exec** | `rm`, `git push`, `sudo` triggered by prompt injection or errant cron | Repo sabotage, file deletion, data loss | Injected instruction: "run: rm -rf /" or "git push" to wrong remote |
| **API overspend** | Rogue tool loops (web_fetch spam, BQ scans) | Budget burn ($50–500+) | Cron malfunction or prompt injection causes 1,000 web_fetch calls |
| **Cron exfiltration** | Compromised cron payload (human error or version control leak) | Sensitive data leaked via scheduled job | Cron sends daily financial snapshot to attacker-controlled webhook |

**Key insight:** The trusted operator (user) is the gatekeeper for legitimate actions. The security model prevents the agent from taking irreversible actions without human approval — it does NOT prevent the user from explicitly instructing the agent to do anything.

### OpenClaw Security Layers

OpenClaw provides multiple configuration points for constraint enforcement:

#### 1. Exec Approvals System

The **exec-approvals.json** file (located at `~/.clawdbot/exec-approvals.sock` on macOS) defines per-agent execution policy:

```json
{
  "version": 1,
  "defaults": {
    "security": "deny",
    "ask": "off"
  },
  "agents": {
    "main": {
      "security": "full",
      "ask": "off"
    },
    "cron": {
      "security": "full",
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
    "security": "full",
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
     "main": { "security": "full", "ask": "off" },
     "cron": { "security": "full", "ask": "off" }
   }
   ```

3. **Assign all crons the same agentId ("cron") so they inherit cron-level policy.** This decouples cron execution from main interactive policy:
   ```bash
   openclaw cron edit <job-id> --set agentId=cron
   ```

**Result:** Crons run with pre-approved binary sets; main agent can prompt on unknown binaries (when ask mode is toggled). Policies are independent — change one without affecting the other.

### Phase 2 (Future): Telegram Approval Prompts

When ready, enable per-action approval via Telegram:

1. Fix `allow-always` persistence bug (pending OpenClaw update)
2. Pre-seed binary allowlist with resolved paths (`which <binary>` on your system)
3. Toggle `ask: "on-miss"` in exec-approvals main agent
4. Configure Telegram target in `openclaw.json` approvals section

**Before Phase 2:** All execs run silently. Phase 2 adds interruptible prompts.

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
    │   (Tier 1 mandatory,                     │
    │    Tier 2 FORCED on every key source)    │
    │                                          │
    ├── Compile spoon-fed brief:               │
    │   - Tier 1+2 findings                    │
    │   - Relevant memory context              │
    │   - User's personal situation            │
    │                                          │
    ├── Spawn sub-agent ──────────────────►  Receives compiled brief
    │   model: GPT (e.g. gpt-5.2)             + analysis task
    │   runTimeoutSeconds: 300                 + output path instruction
    │                                          │
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

Coding tasks are delegated via the **coding-agent skill** and the
**opencode-wrapper skill** rather than raw command invocations. The skills own
the HOW (PTY, tmux session management, background mode, process monitoring,
run-manifest provenance, auto-notify on completion); the orchestrator
(AGENTS.md) owns the project-level constraints.

**Read each skill's SKILL.md before spawning a coding task.** They contain
current command syntax, PTY requirements, and background monitoring patterns
that may change with OpenClaw updates. Hardcoding CLI syntax in AGENTS.md
creates maintenance debt.

**Two complementary skills:**

| Skill | Role |
|-------|------|
| `coding-agent` | Spawns and monitors the coding agent (Codex, Claude Code, opencode, Pi); handles PTY, background mode, and completion detection |
| `opencode-wrapper` | Wraps opencode specifically — manages tmux session naming, log paths, model selection, run-manifest.json, and context threshold routing |

**Preferred agent:** `opencode` via Anthropic provider (`claude-sonnet-4-6`, Thinking: Low).
Other supported agents: Codex, Claude Code (`claude`), Pi.

> **Instance Note (2026-02-23):** Anthropic direct OAuth is broken in some deployments.
> Working fallback: **Google Vertex ADC**. Model: `google-vertex-anthropic/claude-sonnet-4-6@default`.
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
- Skills stay up-to-date with OpenClaw releases (PTY flags, auto-notify pattern, etc.)
- Decouples orchestrator from implementation detail
- Single source of truth for HOW; AGENTS.md only carries project constraints

### Prompt-in-File Standard

When delegating to a coding agent, **always write the prompt to a file**
(e.g., `prompt.txt`) in the project workdir and pass it via stdin or file
argument — never embed long prompts inline in bash.

**Why this matters:** Vague language in inline prompts ("create a module",
"include tests") causes text-only responses — the agent describes what it
would do but writes no files to disk. Explicit, file-based prompts with
clear directives ("write these files to the current working directory") are
reliably executed.

**Pattern:**

```bash
# Write the prompt to a file first
cat > /path/to/project/prompt.txt << 'EOF'
Build a Flask API with the following endpoints...
Write all files to the current working directory.
Include a requirements.txt and README.md.
EOF

# Pass to opencode via stdin or skill wrapper
opencode run --model anthropic/claude-sonnet-4-6 < /path/to/project/prompt.txt
```

**Mandatory phrasing in every prompt:**
- ✅ "Write these files to the current working directory."
- ✅ "Create the following files on disk: ..."
- ❌ "Create a module" (too vague — agent may respond with text only)
- ❌ "Include tests" (too vague — may not write files)

### Run Completion Detection

After spawning a coding agent, check completion before reading output:

```bash
# Primary: tmux session gone = run finished
tmux list-sessions 2>/dev/null | grep <session-name>
# No output = FINISHED

# Fallback: process check
ps aux | grep opencode | grep -v grep
# No output = FINISHED
```

The opencode-wrapper skill writes a `run-manifest.json` to the project
workdir on completion — use this for provenance (model used, tokens, duration).

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
mcporter --config ~/clawd/config/mcporter.json list

# Inspect a server's available tools and schema
mcporter --config ~/clawd/config/mcporter.json list <server-name> --schema

# Preferred call pattern: always use explicit config + JSON args
mcporter --config ~/clawd/config/mcporter.json call "<server-name>.<tool-name>" --args '{"param":"value"}'
```

**Current workspace rule:** always use all 3 pieces together:
1. `--config ~/clawd/config/mcporter.json`
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
mcporter --config ~/clawd/config/mcporter.json call "google-dev-knowledge.search_documents" --args '{"query":"Cloud Run cold start optimization"}'

# Fetch one or more full documents (names come from search results)
mcporter --config ~/clawd/config/mcporter.json call "google-dev-knowledge.get_documents" --args '{"names":["documents/docs.cloud.google.com/run/docs/configuring/healthchecks"]}'
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
mcporter --config ~/clawd/config/mcporter.json call "financial-datasets.getIncomeStatement" --args '{"ticker":"GOOGL","period":"annual","limit":4}'

# Live BTC price
mcporter --config ~/clawd/config/mcporter.json call "financial-datasets.getCryptoPriceSnapshot" --args '{"ticker":"BTC-USD"}'

# Financial metrics (TTM)
mcporter --config ~/clawd/config/mcporter.json call "financial-datasets.getFinancialMetrics" --args '{"ticker":"AAPL","period":"ttm","limit":1}'
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
    Usage: `mcporter --config ~/clawd/config/mcporter.json call "google-dev-knowledge.search_documents" --args '{"query":"..."}'`
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
- `model: haiku`, `thinking: low` — spoon-fed execution, no reasoning needed
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
2. **Skill scan** — Identify every tool or skill likely needed for the pending
   task. Read each relevant `SKILL.md` file. Do not guess syntax from memory.
3. **Confirm back to user** — Report: (a) which memory files were read and any
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
[ ] Model set to haiku with low thinking (confirmed for spoon-fed crons)
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

---

## 9. Revision History

| Date | Change |
|------|--------|
| 2026-03-13 (v12) | **Alignment refresh vs live workspace:** corrected model policy drift (interactive default back to sonnet low; gpt54 overflow; haiku cron-only), updated `gpt54` alias to `github-copilot/gpt-5.4`, replaced stale QMD source-build instructions with live bun package + `better-sqlite3` rebuild flow, updated mcporter examples to the current `--config ... call "server.tool" --args ...` pattern, corrected Google Developer Knowledge tool names (`search_documents`, `get_documents`), updated Financial Datasets count to 17, and documented the 2026.3.11 isolated-cron delivery contract tightening plus issue #43177 false-positive delivery status bug. |
| 2026-03-08 (v11) | **Section 2.5 (NEW):** Added Security Architecture subsection — comprehensive guide to threat model (prompt injection, exfiltration, destructive exec, API overspend), OpenClaw security layers (exec-approvals.json, per-agent isolation, tool policy, message gates), Phase 1 implementation (gateway routing + cron isolation with config example), Phase 2 future state (Telegram approval prompts), and 6 quirks/best practices (binary path resolution, allow-always bug, async approvals, independent eval of ask/security, empty defaults, unicode in crons). Threat model table ranks by likelihood + impact. Config examples are generic (no personal paths/credentials). Links to official exec-approvals, security model, and exec tool docs. |
| 2026-03-08 (v10) | **Section 2 model table:** Updated interactive/conversation thinking from `Low` → `Medium` (haiku thinking:medium is the correct interactive default; crons stay at low). Added `sonnet-gh` alias (`github-copilot/claude-sonnet-4.6`, 125k ctx) to Model Aliases section with usage note. **Section 1 context optimization:** Added `memoryFlush.softThresholdTokens` config recommendation (15,000) with rationale — single large tool response can skip a 4k flush window entirely. **Section 3:** Added Maintenance Cron Pattern subsection — documents the 4-section health report structure (process cleanup, memory backend, token analytics, workspace size), workspace size check script pattern, scheduling guidance, and key payload rules. **Section 4:** Added Non-Trivial Task Gate — mandatory `memory_search` before any research/decision task mid-session. **Section 7:** Added Operational Rituals subsection documenting Prework (3-step: re-boot → skill scan → confirm) and Spa Day / Context Optimization (6-step compaction with MEMORY.md audit). **Section 7 checklist:** Added `wakeMode: "now"` to Cron Creation Checklist (item 13) — prevents scheduler drift; "timezone" property causes drift in Beta. |
| 2026-03-08 (v9) | **Section 1 alignment audit vs official docs:** Added `BOOT.md` entry (gateway-restart checklist, distinct from `HEARTBEAT.md`). Added `BOOTSTRAP.md` to formal file map. Added Workspace Directories section (`skills/`, `canvas/`, `memory/`). Fixed `TOOLS.md` description — added "does not control tool availability" per official docs. Fixed `HEARTBEAT.md` description — added "keep short, token burn risk" per official docs. Fixed injection limit — "~18KB" replaced with official `bootstrapMaxChars: 20,000 chars` + `bootstrapTotalMaxChars: 150,000 chars`. |
| 2026-03-07 (v8) | **Model policy update:** Interactive default switched from `claude-sonnet-4-6` → `claude-haiku-4-5` (sonnet quota burn at 31%/24h unsustainable). Sonnet now explicit-invocation only: deep analysis, high-stakes decisions, complex multi-source synthesis. Updated model table, AGENTS.md, MEMORY.md, TOOLS.md, openclaw.json accordingly. GPT-5-mini documented as zero-quota throwaway option. |
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
