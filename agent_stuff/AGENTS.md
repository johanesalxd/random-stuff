# Agent Directives

Core behavioral directives for AI coding agents. For code style and formatting, see [CODE_STANDARDS.md](./CODE_STANDARDS.md).

## Planning Protocol

- **Plan First:** Start complex tasks in Plan Mode. Focus on logic and architecture before implementation.
- **Fail-Fast:** If implementation breaks, stop immediately. Return to Plan Mode and re-evaluate.
- **Verification:** Use Plan Mode for verification steps, not just building.

## Rule Compounding

- **Continuous Learning:** After every correction or mistake, update instruction files immediately to prevent recurrence.
- **Project Notes:** Maintain notes for every project/task, updated after every PR or significant change.

## Verification and Review

- **Self-Testing:** Do not submit PRs until you have challenged your own changes.
- **Behavioral Diffs:** Prove changes work by diffing behavior between feature branch and main.
- **Confirmation:** After fixing errors, request explicit user confirmation before rerunning tests.

## Subagents and Delegation

- Use subagents for tasks requiring significant compute or multi-step discovery.
- Offload specific tasks to keep the main context window focused and clean.

## Parallelism and Workflows

- Use multiple parallel sessions for independent tasks when available.
- Use git worktrees to switch contexts without losing state.
- Create dedicated analysis worktrees for log reading and data queries.

## Skill and Tool Promotion

- **Automation Rule:** Any task performed more than once daily should be converted into a reusable skill or command.
- **Persistence:** Commit custom skills and commands to git for reuse across projects.
- **CLI-First:** Prefer CLI tools for data retrieval and system analysis.

## Output and Communication

- Use ASCII diagrams or Mermaid for explaining protocols and architecture.
- Provide clear, technical explanations without conversational filler.
- Reference CODE_STANDARDS.md for all code formatting decisions.
