# Changelog

## 2026-04-17 (v17)

- tightened the public memory-tier explanation so L1/L2/L3 stay conceptually clean
- explicitly clarified that `memory_search` is retrieval, not a tier
- explicitly clarified that runtime context/cache is not memory
- compressed the public QMD section to recommendation-level guidance instead of install/runbook detail
- compressed public compaction guidance to architectural rules, leaving operational procedure in workspace protocols
- moved the long historical revision log out of the main guide into this changelog

## 2026-04-16 (v16)

- alignment refresh vs live workspace and latest guide-sync audit
- reframed memory backend guidance around the built-in SQLite + Gemini hybrid default with QMD as optional/rollback
- updated model aliases and assignment examples around Codex-era defaults
- refreshed the multi-agent roster to include the dedicated `opencode` coding lane
- switched public coding guidance from `opencode-acp`-first to `opencode-pty` as the primary lane with ACP as secondary
- corrected ClawHub links to `clawhub.ai`
- added `Skill Execution in Subagents` to the `PROTOCOLS.md` trigger set
- raised the example `memoryFlush.softThresholdTokens` guidance to 25k
- updated the Prework and Spa Day sections to match the current lighter-touch operating model

## 2026-04-06 (v15)

- provider-agnostic refresh
- de-Anthropicized title and intro
- rewrote model strategy around stable aliases and multi-provider routing
- updated execution modes with the built-in-tools-first rule and the Mode 2 `yieldMs` plus `timeout` anti-pattern
- refreshed `WORKSPACE_REFERENCE.md` first so the public guide stayed generic while the personal overlay carried instance-specific truth
- re-ran guide-sync audit against `explore-guide-sync-20260406.txt`
- corrected stale Sonnet/Haiku-era leftovers, skills precedence order, PROTOCOLS/llm-wiki wording, alias examples, multi-agent model rows, and cron-model wording
- renamed the file to `openclaw-public-guide.md`

## 2026-03-31 (v14.2)

- added multi-agent setup and yolo mode section
- documented `vader-yolo` architecture, exec security tiers, `subagents.allowAgents`, yolo UX pattern, and Mode 5
- fixed QMD `includeDefaultMemory=false`, lazy prework skill scan, Tier 1 and Tier 2 pre-flight narration, branch-push policy wording, `opus-av` alias, and six-level skills precedence
- generalized personal references and local paths in the public copy

## 2026-03-21 (v13)

- full alignment refresh vs live workspace and official docs audit
- promoted Gemini Grounding to mandatory Tier 1 research tool
- updated coding architecture from wrapper flow to ACP-era transport and artifacts
- clarified memory tiers: L2 is the full `memory/` folder, L3 is `MEMORY.md`, and `memory_search` is retrieval rather than a tier
- expanded aliases, cron payload fields, approvals notes, and ClawHub references

## 2026-03-13 (v12)

- corrected model policy drift
- updated `gpt54` alias to `github-copilot/gpt-5.4`
- replaced stale QMD source-build instructions with the live bun package plus `better-sqlite3` rebuild flow
- updated mcporter examples and corrected Google Developer Knowledge tool names
- documented isolated-cron delivery tightening and issue #43177 false-positive delivery status bug

## 2026-03-08 (v11)

- added Security Architecture section covering threat model, isolation layers, routing model, approval quirks, and best practices

## 2026-03-08 (v10)

- updated interactive thinking guidance, added `sonnet-gh`, documented `memoryFlush.softThresholdTokens`, maintenance cron pattern, non-trivial task gate, operational rituals, and `wakeMode: "now"`

## 2026-03-08 (v9)

- alignment audit vs official docs
- added `BOOT.md`, `BOOTSTRAP.md`, workspace directories, corrected `TOOLS.md` and `HEARTBEAT.md` descriptions, and fixed injection-limit wording

## 2026-03-07 (v8)

- model policy update to Haiku default at that time, later reverted

## 2026-03-07 (v7)

- added Mermaid diagrams and draw.io edit links

## 2026-03-07 (v6)

- housekeeping alignment across guide, MEMORY.md, TOOLS.md, and config

## 2026-03-07 (v5)

- added QMD search mode note, model providers, aliases, redesigned deep-analysis protocol, coding prompt-in-file standard, run completion detection, and Vertex Gemini SDK notes

## 2026-03-04 (v4)

- added QMD query strategy, context optimization and memory compaction, session reset config, adaptive thinking note, sub-agent permission boundary, deep-analysis protocol, and Financial Datasets MCP example

## 2026-03-02 (v3.1)

- added QMD health-check note using `openclaw memory status`

## 2026-03-01 (v3)

- added STM-as-sole-task-source-of-truth rule and clarified routing of time-bound intel to dated memory files
- expanded research protocol with breaking-event rule, Anchor+Angle, proactive Tier 2, and Deep Research Mode

## 2026-03-01 (v2)

- full rewrite of research tool orchestration into a four-tier architecture

## 2026-03-01

- simplified model strategy and updated boot pattern and research orchestration guidance

## 2026-02-27

- added cron delivery hardening blocks and checklist updates

## 2026-02-25

- added instance-specific notes around Anthropic direct OAuth breakage and Vertex fallback

## 2026-02-23

- added QMD memory backend subsection, cron gotchas, parallel cron support note, and MCP tools integration section

## 2026-02-20

- moved coding guidance toward skill-first delegation

## 2026-02-19

- initial creation, forked from `openclaw-gemini-guide.md`
