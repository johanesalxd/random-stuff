# OpenClaw + Local Models: LM Studio Integration Guide

> Practical patterns for running local models with OpenClaw via LM Studio.
> Covers hardware selection, configuration, and benchmark results comparing
> local MoE models against hosted Anthropic models.
>
> **For general patterns** (workspace architecture, cron design, prompt
> engineering, operational checklists) — see the master guide:
> [OpenClaw + Anthropic Guide](./openclaw-anthropic-guide.md)
>
> **OpenClaw docs:** https://docs.openclaw.ai/gateway/local-models
> **Last updated:** 2026-02-28

---

## 1. Overview

Local models are viable for OpenClaw workloads — but the bar is higher than
typical LLM inference. OpenClaw agents run multi-step agentic loops with tool
calling, file I/O, web search, and long context. Small or aggressively
quantized models raise prompt-injection risk and degrade tool-calling
reliability.

### When Local Makes Sense

- **Coding tasks** — multi-file editing, agentic build loops (opencode)
- **Privacy-sensitive workloads** — data stays on-device
- **Cost reduction** — zero inference cost after hardware
- **Experimentation** — benchmarking model quality against hosted baselines

### When It Doesn't

- **Latency-critical cron jobs** — local models generate thinking tokens before
  every tool call, adding 5-15s per step. A 6-step cron that takes 75s with
  Haiku can take 10+ minutes with a local MoE model.
- **Always-on reliability** — local servers go down when the host sleeps.
  OpenClaw crons fire on schedule regardless; if the model server is offline,
  the job fails silently or falls back to the default model.
- **High-concurrency workloads** — single GPU, single model, one concurrent
  request.

### Hardware Baseline

| GPU VRAM | Viable? | Notes |
|---|---|---|
| 8 GB | ⚠️ Limited | Small dense models only (≤7B Q4). High latency. |
| 16 GB | ✅ Workable | 13-14B Q4_K_M or 7B Q6_K. Decent for light tasks. |
| 24 GB | ✅ Good | 27B dense Q4 or 35B MoE Q4_K_M at 65K context. |
| 32 GB | ✅ Recommended | 35B MoE Q4_K_M at 128K context comfortably. |
| 48 GB+ | ✅ Excellent | Full Q6/Q8 variants, longer context, lower latency. |

OpenClaw's own docs recommend ≥2× maxed-out Mac Studios (~$30k) for
production. For experimentation, a single 24-32 GB GPU is sufficient.

---

## 2. LM Studio Setup

### Install and Load

1. Download LM Studio from [lmstudio.ai](https://lmstudio.ai)
2. Download your target model (see Section 5 for model selection)
3. Load the model in the **My Models** tab
4. Enable the local server: **Developer** tab → toggle **Server Running**

### Optimal Server Configuration

These settings are validated on a 32 GB GPU with Qwen3.5 35B A3B Q4_K_M:

| Setting | Recommended Value | Notes |
|---|---|---|
| Context Length | 65536–131072 | Start at 65K; increase if VRAM allows |
| GPU Offload | All layers | Max GPU utilization |
| Max Concurrent Predictions | 1 | Single-user; avoids KV cache multiplier |
| Flash Attention | ON | Reduces attention memory usage |
| K/V Cache Quantization | q8_0 | Saves ~2-3 GB VRAM, negligible quality loss |
| Offload KV Cache to GPU | ON | Keep KV cache on GPU |
| Keep Model in Memory | ON | Avoids cold-load latency |
| Auto Unload If Idle | OFF or long TTL | Prevents silent failures during cron runs |

### VRAM Estimation by Context

For Qwen3.5 35B A3B Q4_K_M on 32 GB:

| Context Length | Est. VRAM (KV q8_0 ON) | Headroom |
|---|---|---|
| 65,536 | ~25 GB | ~7 GB ✅ |
| 131,072 | ~25.2 GB | ~6.8 GB ✅ |
| 196,608 | ~27 GB | ~5 GB ⚠️ |
| 262,144 (native max) | ~29+ GB | ~3 GB ❌ tight |

### Verify Server is Running

```bash
curl http://127.0.0.1:1234/v1/models
```

Should return a JSON list of loaded model IDs.

---

## 3. OpenClaw Integration

### Add the Provider

In `~/.openclaw/openclaw.json`, add to `models.providers`:

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "lmstudio": {
        "baseUrl": "http://127.0.0.1:1234/v1",
        "apiKey": "lmstudio",
        "api": "openai-responses",
        "models": [
          {
            "id": "your-model-id",
            "name": "Your Model Name",
            "reasoning": true,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 8192
          }
        ]
      }
    }
  }
}
```

Replace `your-model-id` with the exact ID returned by `/v1/models`.
Use `"mode": "merge"` to keep hosted models available as fallbacks.

**Remote host:** If LM Studio runs on a different machine on your LAN,
replace `127.0.0.1:1234` with the machine's LAN IP (e.g. `192.168.1.x:1234`).
Ensure LM Studio is bound to `0.0.0.0` and your firewall allows port 1234.

### Add to Agent Model Allowlist

OpenClaw crons and isolated agents enforce a model allowlist. Without this
step, the model silently falls back to the agent default with a log warning:

```
payload.model 'lmstudio/your-model-id' not allowed, falling back to agent defaults
```

Add the model to `agents.defaults.models` in `openclaw.json`:

```json
{
  "agents": {
    "defaults": {
      "models": {
        "lmstudio/your-model-id": {
          "alias": "local-model"
        }
      }
    }
  }
}
```

### Restart Gateway

After editing `openclaw.json`:

```bash
openclaw gateway restart
openclaw gateway status
```

Verify `RPC probe: ok` before proceeding.

### Use in a Cron Job

```bash
openclaw cron add \
  --name "My Cron" \
  --cron "0 9 * * *" \
  --session isolated \
  --model "lmstudio/your-model-id" \
  --thinking low \
  --announce \
  --channel telegram \
  --to <your-chat-id> \
  --best-effort-deliver \
  --message "Your prompt here"
```

> ⚠️ See Section 8 (Cron Compatibility) before using local models for crons.

---

## 4. opencode Integration

For coding agent sessions via opencode, add to `~/.config/opencode/opencode.json`:

```json
{
  "provider": {
    "lmstudio": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "LM Studio (local)",
      "options": {
        "baseURL": "http://127.0.0.1:1234/v1"
      },
      "models": {
        "your-model-id": {
          "name": "Your Model Name",
          "context": 131072
        }
      }
    }
  }
}
```

Use in opencode by selecting:
```
lmstudio/your-model-id
```

The `context` field tells opencode when to trigger compaction — set it to
match your LM Studio context window setting to avoid hitting the hard server
limit before compaction fires.

---

## 5. Model Selection Guide

### Dense vs MoE

| Architecture | Example | Active Params | Speed | Quality | VRAM |
|---|---|---|---|---|---|
| Dense | Qwen3.5 27B | 27B/token | Slower | Good | Lower |
| MoE | Qwen3.5 35B A3B | ~3B/token | **Faster** | **Better** | Higher |

MoE wins on quality and speed for most tasks. The "3B activated" vs "27B
active" comparison is misleading — MoE routing selects the **best 3B of 35B**
for each token. Dense 27B uses all 27B, always, with no specialization.

Dense wins only when VRAM is very tight and you need longer context — its
lower footprint leaves more room for the KV cache.

### Quantization Levels

| Quant | Bits/weight | Quality | Use case |
|---|---|---|---|
| Q2_K | ~2.6 | ❌ Degraded | Not recommended |
| Q3_K_M | ~3.3 | ⚠️ Acceptable | Memory-constrained only |
| Q4_K_M | ~4.5 | ✅ Sweet spot | Best quality/size ratio |
| Q5_K_M | ~5.5 | ✅✅ Near-lossless | If VRAM allows |
| Q6_K | ~6.6 | ✅✅✅ Excellent | Smaller dense models |
| Q8_0 | ~8.5 | ≈ FP16 | Benchmarking only |

**The K suffix matters:** K-quants are smarter — they preserve higher precision
on important weights. Always prefer `Q4_K_M` over plain `Q4_0`.

### Qwen3.5 35B A3B Architecture Notes

- 40 layers total: 30 × Gated DeltaNet (linear attention, O(n) context cost)
  + 10 × standard attention with KV cache
- Native context: 262K tokens
- Active experts: 8 per token (64 total expert pool)
- Thinking mode: generates `<think>` blocks before every response
- Q4_K_M file size: ~22 GB; fits in 32 GB with room for KV cache

---

## 6. Benchmark Results

Three tasks run across Anthropic Haiku, Anthropic Sonnet, and a local
MoE model (Qwen3.5 35B A3B Q4_K_M @ 128K context via LM Studio).
All runs used identical prompts and the opencode coding agent.

### Task A: Codebase Modernization (existing repo)

Prompt: Replace legacy MCP toolset with ADK built-in BigQueryToolset,
upgrade dependencies, delete obsolete folders, update README.

| Check | Sonnet | Haiku | Local MoE |
|---|---|---|---|
| Core task correct | ✅ | ✅ | ✅ |
| Idiomatic imports | ✅ | ✅ | ❌ non-standard |
| Docstrings accurate | ✅ | ❌ stale | ❌ stale |
| Dep versions preserved | ❌ | ❌ | ❌ |
| Sub-files touched | ✅ | ✅ | ❌ missed |
| .env.example updated | ✅ | ✅ | ❌ missed |
| Steers needed | 0 | 0 | **0** |
| Self-correction | ✅ | ✅ | ✅ (1 error) |

**Finding:** Local MoE completed the core task with zero steers and
self-corrected a casing error. Missed peripheral files. Sonnet and Haiku
tied for first; local MoE ~75% of gold standard.

### Task B: From-Scratch Python App (CLI tool)

Prompt: Research public APIs, build typer CLI + async httpx fetcher + reporter,
write tests with mocked HTTP, README, DECISIONS.md, commit.

| Dimension | Haiku | Local MoE |
|---|---|---|
| Works out of the box | ✅ | ❌ async CLI bug |
| Architecture quality | Good | **Better** (dataclasses, custom exceptions) |
| Test count | 18 | 29 |
| Test mock approach | AsyncMock | pytest-httpx (more correct) |
| Timezone-aware timestamps | ❌ | ✅ |
| Logging module | ❌ | ✅ |
| .gitignore created | ✅ | ✅ (after prompt hint) |
| DECISIONS.md quality | ✅✅ | ✅ |
| Steers needed | **0** | 1 (async mock hint) |
| Visible reasoning steps | No | Yes (91 think blocks) |

**Finding:** Local MoE designed better architecture but shipped a broken
entrypoint (`async def` commands without `asyncio.run()` wrapper). Haiku
wrote simpler code that actually ran. Local MoE needed 1 steer.

### Task C: Agentic Tool-Calling (multi-phase intelligence report)

Same prompt, same config. Run as an OpenClaw isolated cron job.

| Metric | Haiku | Local MoE |
|---|---|---|
| Tool sequence correct | ✅ | ✅ |
| Phases followed | ✅ | ✅ |
| Runtime | ~75s | 10min (timeout) |
| Delivery success | ✅ | ❌ timed out |

**Finding:** Local MoE followed the manifest correctly but timed out before
completing. Thinking token overhead (~1K tokens per step × 6+ tool calls)
consumed the entire time budget. See Section 8.

---

## 7. Where Local Models Shine

- **Coding tasks in opencode** — zero-steer agentic builds, multi-file edits,
  test writing. Quality gap vs Sonnet is real but narrow on well-specified tasks.
- **Architecture decisions** — local MoE tends to produce better-structured
  code (dataclasses, custom exceptions, proper separation of concerns) vs
  Haiku's pragmatic style.
- **Research-first tasks** — the visible `<think>` chain is an asset when you
  want to audit reasoning. Local MoE web-searched APIs before writing code.
- **Cost** — zero inference cost once hardware is paid for. Long sessions,
  many iterations, no quota pressure.
- **Privacy** — data never leaves the machine.

---

## 8. Cron Compatibility

**Short answer: do not use local models for latency-sensitive crons.**

OpenClaw crons run in isolated sessions with a timeout. Local MoE models
generate visible reasoning tokens (`<think>` blocks) before every tool call.
A 6-step cron prompt that takes 75s with Haiku takes 10+ minutes with a
local MoE model because:

- Each `<think>` block: ~1,000–1,500 tokens = several seconds at ~145 tok/s
- 6 tool calls × ~10s think overhead = ~60s thinking alone, before any
  actual tool execution

**Additional reliability risks for crons:**

1. **Host sleep** — if the machine running LM Studio goes to sleep, the model
   server becomes unreachable. OpenClaw crons fire regardless. Set your OS
   power plan to prevent sleep while the server is meant to be up.
2. **Model unloaded** — LM Studio may unload the model after inactivity. Set
   TTL to a long value or disable auto-unload.
3. **Cold load latency** — if the model was unloaded, the first request
   triggers a cold load that can take 10-30s before inference begins.

**Recommendation:** Use local models for interactive opencode sessions.
Keep hosted models (Haiku is ideal) for all scheduled cron jobs.

---

## 9. Known Gotchas

### Model Not Allowed in Isolated Sessions

**Symptom:** Log shows `payload.model 'lmstudio/...' not allowed, falling back to agent defaults`

**Fix:** Add the model to `agents.defaults.models` in `openclaw.json` (see Section 3).
This is separate from `models.providers` — both blocks are required.

### Missing `--to` Flag on Cron Add

**Symptom:** Cron runs but announce delivery goes nowhere.

**Fix:** Always pass `--to <chat-id>` when creating crons via `openclaw cron add`.
The delivery block requires the `to` field for announce routing.

```bash
# Correct
openclaw cron add --announce --channel telegram --to <chat-id> ...

# Missing --to: announce fires but delivers nowhere
openclaw cron add --announce --channel telegram ...
```

### Context Exhaustion vs Compaction

opencode triggers compaction when context approaches the configured limit.
But LM Studio enforces a **hard server-side limit** — if the model hits it
before opencode compacts, LM Studio kills the process. The compaction prompt
never runs.

**Fix:** Set `context` in `opencode.json` to match your LM Studio context
window. This tells opencode to compact earlier, before hitting the hard wall.

### Tool Argument Serialization (Double-Quoting)

**Symptom:** `message failed: Unknown target ""1636474175""` — double quotes.

**Root cause:** Some local models serialize integer arguments as quoted strings
when calling tools. Anthropic models pass them as bare integers.

**Fix:** Add explicit clarification in prompts: `target value is the bare
number, no quotes`. Or rely on `delivery.mode: announce` fallback instead
of instructing the model to call the message tool directly.

### pycache Committed to Git

Local models may not create `.gitignore` unless explicitly instructed.

**Fix:** Include in your prompt:
> "Create a .gitignore that excludes `__pycache__`, `*.pyc`, `.venv`, `*.egg-info`"

---

## 10. Quick Reference

### Minimal openclaw.json provider + allowlist

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "lmstudio": {
        "baseUrl": "http://127.0.0.1:1234/v1",
        "apiKey": "lmstudio",
        "api": "openai-responses",
        "models": [{
          "id": "your-model-id",
          "name": "Your Model",
          "reasoning": true,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 131072,
          "maxTokens": 8192
        }]
      }
    }
  },
  "agents": {
    "defaults": {
      "models": {
        "lmstudio/your-model-id": { "alias": "local" }
      }
    }
  }
}
```

### Minimal opencode.json provider block

```json
{
  "provider": {
    "lmstudio": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "LM Studio (local)",
      "options": { "baseURL": "http://127.0.0.1:1234/v1" },
      "models": {
        "your-model-id": {
          "name": "Your Model",
          "context": 131072
        }
      }
    }
  }
}
```

### Health check before use

```bash
# Verify LM Studio server
curl http://127.0.0.1:1234/v1/models

# Verify OpenClaw gateway
openclaw gateway status

# Quick inference test
curl http://127.0.0.1:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "your-model-id", "input": "Hello"}'
```
