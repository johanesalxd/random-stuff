# OpenClaw + Gemini: Gotchas & Lessons Learned

> Companion guide for running OpenClaw with Google Gemini models.
> Covers Gemini-specific setup, model selection, and known gotchas.
>
> **For general patterns** (workspace architecture, cron design, prompt
> engineering, operational checklists) — see the master guide:
> [OpenClaw + Anthropic Guide](./openclaw-anthropic-guide.md)
>
> **OpenClaw docs:** https://docs.openclaw.ai/
> **Last updated:** 2026-03-01

---

## 1. Gemini's Role in the Stack

Gemini is **not** the primary agent model — Anthropic Sonnet/Haiku/Opus
handle all conversation, cron, and coding tasks. Gemini's current role:

- **Gemini CLI as proxy layer** — headless analytics and BigQuery tasks
  delegated by the primary agent (see Section 4)
- **Vertex ADC fallback** — available as a provider for opencode coding
  sessions, but benchmarked below Sonnet (see Section 5)

If you're evaluating Gemini as a primary agent, read Section 5 first.

---

## 2. Provider Setup (Google Vertex ADC)

### Prerequisites

- Google Cloud project with Vertex AI API enabled
- Application Default Credentials configured:
  ```bash
  gcloud auth application-default login
  ```
- ADC file at: `~/.config/gcloud/application_default_credentials.json`

### openclaw.json Provider Block

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "google-vertex": {
        "project": "your-gcp-project-id",
        "location": "global",
        "models": [
          {
            "id": "gemini-3.1-pro-preview-customtools",
            "name": "Gemini 3.1 Pro (customtools)",
            "input": ["text"],
            "contextWindow": 1048576,
            "maxTokens": 65536
          }
        ]
      }
    }
  }
}
```

> ⚠️ **`location: global` is required for Gemini 3.1 Pro preview.**
> `us-east5`, `us-central1`, `us-east4`, and `us-west1` all return
> model-not-found. This is not documented — `global` is the only working
> value for preview models.

### Separate Vertex Blocks for Gemini vs Claude-on-Vertex

If you also run Claude models via Vertex (`google-vertex-anthropic` provider),
keep them in **separate provider blocks**. They use different auth paths and
model namespaces:

```json
"google-vertex-anthropic": {
  "project": "your-gcp-project-id",
  "location": "us-east5",
  ...
},
"google-vertex": {
  "project": "your-gcp-project-id",
  "location": "global",
  ...
}
```

> ⚠️ Claude Sonnet 4.x on Vertex is NOT available in `us-central1` or
> `global`. Use `us-east5` for Claude-on-Vertex.

### opencode.json Provider Block

```json
{
  "provider": {
    "google-vertex": {
      "project": "your-gcp-project-id",
      "location": "global",
      "models": {
        "gemini-3.1-pro-preview-customtools": {
          "name": "Gemini 3.1 Pro (customtools)",
          "context": 131072
        }
      }
    }
  }
}
```

---

## 3. Model Selection

### Flash vs Pro

| Aspect | Gemini Flash | Gemini Pro |
|--------|-------------|------------|
| Latency | Low (~1–3s) | Higher (~5–15s) |
| Cost | Significantly cheaper | ~10–20× more expensive |
| Context window | 1M tokens | 1M+ tokens |
| Reasoning depth | Good for structured tasks | Better for complex synthesis |
| Cron compatible | ✅ Yes | ❌ No — too slow (see Section 6) |
| Best for | Automation, quick responses | Deep analysis, research |

### Thinking Budget Levels

| Level | When to Use |
|-------|-------------|
| Low | Cron jobs, spoon-fed prompts, atomic steps |
| Medium | Interactive conversation, moderate complexity |
| High | Complex research, multi-step synthesis |

**Rule:** If the prompt already tells the model what to do step-by-step,
use low thinking. Save medium/high for open-ended tasks where the model
must reason about the plan, not just execute it.

### The `customtools` Model Variant

Use `gemini-3.1-pro-preview-customtools`, **not** the standard
`gemini-3.1-pro-preview`, for any task involving custom tool calling.

**Why:** Google shipped a separate `customtools` model variant to fix a
documented issue where Gemini Pro ignores custom tool definitions and
defaults to bash. The standard variant loops on the plan without executing
tools reliably. The `customtools` variant resolves this.

This is set in `~/.gemini/settings.json`:
```json
{
  "model": "gemini-3.1-pro-preview-customtools"
}
```

---

## 4. Gemini CLI as Proxy Layer

The Gemini CLI (`gemini`) runs headlessly as an analytics proxy, delegated
by the primary Vader/OpenClaw agent. This keeps Gemini's BQ and Workspace
extensions available without making it the primary orchestrator.

### Headless Mode

```bash
gemini -p "your prompt here"
```

The `-p` flag runs non-interactive. Tool calls fire identically to the
interactive TUI — confirmed parity.

For tasks requiring file system access or multi-step tool calls:

```bash
gemini -p "your prompt" --approval-mode yolo
```

`--approval-mode yolo` auto-approves all tool calls (equivalent to
"approve for this session" in the TUI). Required for agentic flows.

### Working Directory

Run from `~/Developer/git` — this is a Gemini CLI trusted folder,
pre-authorized for file access. Running from other directories may
trigger permission prompts even in headless mode.

### BigQuery via Gemini CLI

Gemini's `bigquery-data-analytics` extension handles BQ queries natively.
Pass env vars explicitly — they are not inherited from `.zshrc` in exec
context:

```bash
BIGQUERY_PROJECT=your-project BIGQUERY_LOCATION=US \
  gemini -p "your BQ prompt" --approval-mode yolo
```

Default BQ location: `US` (multi-region). Specify `asia-southeast1` or
other regions explicitly per task if needed.

### Installed Extensions

- `bigquery-conversational-analytics`
- `bigquery-data-analytics`
- `DeveloperKnowledge`
- `google-workspace`

---

## 5. Benchmark Notes (Gemini vs Sonnet)

From the `bq-agent-app` benchmark (Feb 2026) — same ADK modernization task,
same repo, head-to-head:

| Dimension | Claude Sonnet (Vertex) | Gemini 3.1 Pro (customtools) |
|-----------|----------------------|------------------------------|
| Core task correct | ✅ | ✅ |
| Files changed | 11 files, 543 insertions | 9 files, 242 insertions |
| Time to complete | ~18 min | ~45 min |
| Steers needed | 0 | 2 (import error + session restart) |
| Out-of-scope changes | None | Yes |
| Tests passing | 5/5 | 2/5 |
| Pattern consistency | ✅ | ❌ inconsistent |
| Self-correction | ✅ (via source introspection) | ⚠️ partial |
| SWE-Bench Verified | 1,633 pts | 1,317 pts (−24%) |

**Verdict:** Sonnet wins on every practical dimension. Gemini Pro is faster
to configure and more concise, but unreliable for complex ADK patterns.
The 24% SWE-Bench gap is real and observable in agentic coding tasks.

**When Gemini outperforms:** Short, structured, tool-assisted analytics
(BQ queries, Workspace operations). These play to its extension ecosystem
and don't stress the tool-calling reliability issues.

---

## 6. Cron Compatibility

**Use Flash only for crons. Do not use Pro.**

OpenClaw crons have approximately a 60-second execution timeout. Gemini Pro
models add 5–15s latency per step. A 6-step cron payload that completes in
75s with Haiku will time out with Pro.

Flash with low thinking fits comfortably within the window and handles
well-structured spoon-fed payloads reliably.

For cron architecture and payload patterns, see the
[Anthropic guide, Section 3](./openclaw-anthropic-guide.md).

---

## 7. Known Gotchas

### Tool Calling Failures (Pro Standard Variant)

**Symptom:** Model ignores custom tool definitions, defaults to bash,
or loops on the plan without executing tool calls.

**Fix:** Use `gemini-3.1-pro-preview-customtools` — not the standard
`gemini-3.1-pro-preview`. Set it in `~/.gemini/settings.json`.

### `location: global` Required for Pro Preview

**Symptom:** `model not found` error when configuring Gemini 3.1 Pro on Vertex.

**Fix:** Set `"location": "global"` in both `openclaw.json` and
`opencode.json` provider blocks. All regional endpoints (`us-east5`,
`us-central1`, etc.) return model-not-found for preview models.

### Out-of-Scope Edits in opencode Sessions

**Symptom:** Gemini makes changes to files not mentioned in the task prompt.

**Mitigation:** Be explicit about scope in the prompt:
> "Only modify files directly required for [task]. Do not touch files
> outside this scope."

### Session Restart Needed on Import Errors

**Observed:** Gemini Pro sometimes requires a full session restart after
hitting an import or dependency error — it doesn't self-correct by
re-reading source files the way Sonnet does. If the session loops on the
same error after one correction attempt, restart.

### Gemini CLI Env Vars Not Inherited

**Symptom:** BQ queries fail with missing project/credentials errors when
running via `exec`.

**Fix:** Pass env vars explicitly on the command line:
```bash
BIGQUERY_PROJECT=your-project BIGQUERY_LOCATION=US gemini -p "..."
```
Do not rely on `.zshrc` exports — they are not available in OpenClaw's
exec context.

---

## 8. Quick Reference

### Vertex Provider Config (openclaw.json)

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "google-vertex": {
        "project": "your-gcp-project-id",
        "location": "global",
        "models": [{
          "id": "gemini-3.1-pro-preview-customtools",
          "name": "Gemini 3.1 Pro (customtools)",
          "input": ["text"],
          "contextWindow": 1048576,
          "maxTokens": 65536
        }]
      }
    }
  }
}
```

### Gemini CLI Headless Commands

```bash
# Non-interactive one-shot
gemini -p "your prompt"

# With auto-approved tool calls (agentic tasks)
gemini -p "your prompt" --approval-mode yolo

# BigQuery with explicit env
BIGQUERY_PROJECT=your-project BIGQUERY_LOCATION=US \
  gemini -p "query BQ: ..." --approval-mode yolo
```

### Model Assignment

| Context | Model | Thinking |
|---------|-------|----------|
| Cron / Automation | `gemini-flash` | Low |
| Interactive / Coding | `gemini-3.1-pro-preview-customtools` | Medium |
| BQ / Analytics (CLI proxy) | Set in `~/.gemini/settings.json` | — |
