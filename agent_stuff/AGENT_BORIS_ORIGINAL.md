# Boris Cherny's Claude Code Directives

These directives are sourced from the Claude Code team to maximize productivity and minimize error rates.

## 1. Workflows and Parallelism
- Use multiple parallel sessions for independent tasks.
- Utilize git worktrees to switch contexts without losing state.
- Create dedicated "analysis" worktrees for log reading and data queries.

## 2. Plan Mode Protocol
- **Mandatory Planning:** Start every complex task in Plan Mode. Focus 100% of effort on the logic/architecture before moving to implementation.
- **Verification:** Use Plan Mode for verification steps, not just for building.
- **Fail-Fast:** If an implementation goes sideways, stop immediately. Switch back to Plan Mode and re-plan.

## 3. Rule Compounding (The Feedback Loop)
- **Continuous Improvement:** After every correction or mistake, update your instruction file (e.g., AGENTS.md) immediately to prevent the error from recurring.
- **Note Maintenance:** Maintain a notes directory for every project/task, updated after every PR.

## 4. Skill and Tool Promotion
- **Automation Rule:** Any task performed more than once a day must be converted into a skill or command.
- **Git Persistence:** Commit your custom skills and slash commands to git for reuse across projects.

## 5. Subagents and Delegation
- Use "use subagents" for tasks requiring significant compute or multi-step discovery.
- Offload specific tasks to subagents to keep the main agent's context window focused and clean.

## 6. Verification and Review
- **Self-Testing:** Do not make a PR until you have challenged your own changes.
- **Behavioral Diffs:** Prove changes work by diffing behavior between the feature branch and main.

## 7. Data and Analytics
- Use CLI tools (e.g., `bq`, `docker logs`) to pull metrics and troubleshoot distributed systems on the fly.
- Leverage MCPs (e.g., Slack) to ingest bug threads or external context directly.

## 8. Learning and Output Styles
- Use specialized output styles (e.g., /config learning) to explain the logic behind changes.
- Use ASCII diagrams or visual HTML presentations to explain unfamiliar protocols/codebases.
