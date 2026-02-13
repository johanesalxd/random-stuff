# Agent Directives

Core behavioral directives for AI coding agents. For code style and formatting, see [CODE_STANDARDS.md](./CODE_STANDARDS.md).

## Planning Protocol

- **Plan First:** Start complex tasks in Plan Mode. Focus on logic and architecture before implementation.
- **Fail-Fast:** If implementation breaks, stop immediately. Return to Plan Mode and re-evaluate.
- **Verification:** Use Plan Mode for verification steps, not just building.

## Context Management

- **Task Tracking:** Use TodoWrite to plan and track multi-step tasks. Break complex work into smaller steps and mark progress as you go.
- **Subagent Delegation:** Delegate codebase exploration, multi-file searches, and independent parallel workstreams to subagents. Keep the main context focused on the primary task.
- **Context Budget:** Be aware that system prompts, instruction files, and tool definitions consume context. Avoid unnecessary tool calls that return large outputs when a targeted search suffices.

## Rule Compounding

- **Continuous Learning:** After every correction or mistake, suggest updates to instruction files for user review. Do not modify instruction files without explicit approval.

## Verification and Review

- **Self-Testing:** Do not submit PRs until you have challenged your own changes.
- **Regression Check:** Run tests against both main and feature branch to verify no regressions before submitting changes.
- **Confirmation:** After fixing errors, request explicit user confirmation before rerunning tests or commands.

## Decision Making

- **Ask vs. Assume:** Ask clarifying questions rather than making large assumptions about user intent. Small, obvious decisions can be made autonomously.
- **Instruction Precedence:** Project-level rules (AGENTS.md in repo) take precedence over global rules when they conflict. Note the conflict and follow the project-level rule.
- **Uncertainty:** When uncertain about an approach, investigate the codebase first rather than guessing. Use grep, glob, and file reads to gather evidence before proposing solutions.

## Subagents and Delegation

- Use subagents for tasks requiring significant compute or multi-step discovery.
- Offload specific tasks to keep the main context window focused and clean.

## Parallelism and Workflows

- Use multiple parallel sessions for independent tasks when available.
- Consider git worktrees when working across multiple branches simultaneously.

## Skill and Tool Promotion

- **Automation Rule:** When the user indicates a task is repetitive, or when a pattern repeats within a session, suggest converting it into a reusable skill or command.
- **Persistence:** Commit custom skills and commands to git for reuse across projects.
- **CLI-First:** Prefer CLI tools for data retrieval and system analysis.

## Output and Communication

- Use ASCII diagrams or Mermaid for explaining protocols and architecture.
- Provide clear, technical explanations without conversational filler.
- Reference CODE_STANDARDS.md for all code formatting decisions.
