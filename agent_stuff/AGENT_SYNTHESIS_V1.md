# Agent Core Directives (Synthesis V1)

This document merges Google Engineering Standards with the Boris Agentic Workflow. 

## 1. Operational Directives
- **Plan Mode First:** Start all complex tasks in Plan Mode. Pour energy into the logic so implementation is a one-shot success.
- **Fail-Fast:** Stop implementation immediately if logic breaks. Return to Plan Mode and re-evaluate.
- **Rule Compounding:** Update this file (or the relevant instruction set) immediately after any correction to prevent repeated mistakes.
- **Subagent Offloading:** Use subagents for multi-step discovery or to keep the main context window clean.

## 2. Coding and Quality Standards
- **Style Guides:** Follow Google official style guides for Python, Go, Java, and TypeScript.
- **Naming:** Use semantic naming. No abbreviations unless industry standard.
- **Documentation:** Document all public APIs (Args, Returns, Raises). Private functions must be documented if logic is non-obvious.
- **Functionality:** Keep functions focused, single-purpose, and generally under 50 lines.

## 3. Security Protocols
- **Secrets:** Never hardcode credentials. Use environment variables or secret managers.
- **Input:** Validate all user input (Allowlists > Denylists).
- **Injection:** Use parameterized queries for all database interactions.
- **Sanitization:** Sanitize all output to prevent XSS.

## 4. Testing and Verification
- **AAA Pattern:** Arrange, Act, Assert.
- **Self-Review:** Challenge your own changes. Do not submit PRs until verification tests pass.
- **Mocking:** Mock all external dependencies (APIs, DBs, Cloud).

## 5. Tooling and Skills
- **Skill Promotion:** Any task performed >1x daily must be turned into a skill or command and committed to Git.
- **CLI-First:** Prioritize CLI tools (`bq`, `gh`, `docker`) for data retrieval and system analysis.
- **Mermaid:** Use Mermaid syntax for all architectural or flow diagrams.

## 6. Git and Workflow
- **Atomic Commits:** One logical change per commit.
- **Messages:** Use `<type>: <subject>` format (imperative mood, max 50 chars).
- **Worktrees:** Use git worktrees to run multiple sessions in parallel across tasks.
