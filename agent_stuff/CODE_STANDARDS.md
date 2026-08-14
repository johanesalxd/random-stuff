# Code Standards

Fallback standards for AI-assisted engineering. Apply only relevant sections.

## Authority

1. Explicit user and task requirements.
2. Repository-local instructions and documented conventions.
3. Checked-in formatter, linter, compiler, build, tests, CI, lockfile, and nearby code.
4. Google's published style guides.
5. Official language, web-platform, accessibility, and security guidance.
6. This file.

Do not migrate established tooling or reformat unrelated code. Generated and vendored code follows its generator or upstream source.

## Reference Baseline

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Google Go Style Guide](https://google.github.io/styleguide/go/)
- [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html)
- [Google JavaScript Style Guide](https://google.github.io/styleguide/jsguide.html)
- [Google HTML/CSS Style Guide](https://google.github.io/styleguide/htmlcssguide.html)
- [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) and [OWASP Cheat Sheets](https://cheatsheetseries.owasp.org/)

Google style is the north star, not a reason to fight repository tooling or current platform standards.

## Common Engineering Defaults

### Design and Scope

- Prefer clear, direct code over cleverness and speculative abstraction.
- Keep changes focused. Preserve compatibility unless the task intentionally changes it.
- Avoid hidden global state, surprising side effects, and duplicated authorities.

### Errors, Resources, and Data

- Handle errors where context can be added or recovery is possible; do not silently discard them.
- Preserve causal context when wrapping or translating failures.
- Define cleanup for files, processes, locks, connections, goroutines, tasks, and temporary resources.
- Validate external data for type, shape, range, encoding, and business invariants at trust boundaries.
- Importers, generators, migrations, and validators must fail closed on required schemas, counts, uniqueness, relationships, and integrity checks.
- Never report success independently of the computed result being validated.

### Security and Privacy

- Never embed or log credentials, tokens, session IDs, private keys, connection strings, or unnecessary personal data.
- `.gitignore` is not secret storage and does not remove exposed history.
- Prefer project-approved secret management or runtime-mounted/in-memory injection. Use environment variables only when appropriate to the threat model; never expose secrets in definitions, logs, dumps, or process arguments.
- Provide a placeholder-only `.env.example` for reusable projects.
- Use parameterized data access, contextual output encoding, and established cryptographic and identity libraries.
- Avoid dynamic code execution and unsafe deserialization of untrusted input.
- Use least privilege and secure defaults. Do not disable certificate checks, authentication, authorization, CSRF protection, or other safeguards as a workaround.
- Authentication and authorization differ; choose OAuth, OIDC, sessions, and token formats from verified requirements.

### Testing

- Test observable contracts, meaningful decisions, failure paths, and boundaries—not coverage numbers or framework internals.
- Choose unit, integration, contract, end-to-end, property, and visual tests according to risk.
- Prefer real values, fakes, or lightweight implementations. Mock external or nondeterministic boundaries when useful.
- Assert exact values and invariants when exactness is the contract. Add negative tests for fail-closed validators.
- Keep tests deterministic, independent, readable, and explicit about the scenario.
- Distinguish regressions from pre-existing failures. After fixes, rerun affected checks and the relevant final suite.

### Dependencies and Documentation

- Follow the repository's package manager and lockfile. Lock deployable applications; libraries may need compatible ranges.
- Use actual ecosystem vulnerability tooling; integrity checks are not vulnerability scans.
- Document prerequisites, setup, configuration, verification, and operational constraints for the intended audience.
- Keep reusable documentation portable: no personal paths, private-service assumptions, or secrets.

## Python

- Respect the declared Python version and existing packaging configuration.
- For greenfield applications, prefer `pyproject.toml`, `uv`, Ruff, and pytest when they fit. Do not migrate an established toolchain without explicit scope.
- Let configured formatters and linters control layout, imports, and line length.
- Use type hints where they clarify interfaces. Match syntax to the minimum supported version.
- Prefer built-in generics and `X | None` when supported. Use the full typing toolkit when it expresses the contract.
- Prefer `collections.abc` for applicable runtime protocols and abstractions.
- Keep imports explicit and consistently grouped; avoid wildcard imports.
- Use Google-style docstrings for public APIs and non-obvious behavior. Do not repeat a clear signature.
- Use lazy logging arguments where supported. Never log secrets or unnecessary personal data.
- Raise specific exceptions, preserve causes, and avoid broad catches unless adding context, cleanup, or a deliberate boundary.
- Use context managers or `try/finally` for owned resources. Avoid mutable defaults and hidden import-time side effects.
- Run the repository's tests, lint, type checks, build, and configured dependency scanner such as `pip-audit`.

## Go

- Format changed code with `gofmt`; use `goimports` only when the project does.
- Follow package-local API and naming conventions.
- Use consistent initialism spelling rather than a blanket all-caps rule.
- Return errors for expected failures. Add context and preserve identity with `%w` when callers need `errors.Is` or `errors.As`.
- Pass `context.Context` explicitly, normally first. Store it in structs only for a narrow, documented compatibility constraint.
- Make goroutine lifetime, channel ownership, and shutdown behavior clear.
- Document all top-level exported names; explain contracts, behavior, constraints, and side effects rather than restating declarations.
- Prefer composition and small interfaces defined near consumers.
- Run relevant tests, `go vet`, configured linters, and `go test -race` for concurrency changes.
- Use `govulncheck ./...` or the configured scanner. `go mod verify` checks module integrity, not known vulnerabilities.
- Use table-driven tests when cases share meaningful setup; do not force unrelated scenarios into a table.

## TypeScript and JavaScript

- Follow the repository's language version, modules, package manager, lockfile, formatter, linter, framework, and tests.
- Prefer TypeScript for new application code when supported; do not convert established JavaScript incidentally.
- Let checked-in tooling control quotes, semicolons, indentation, imports, and line length.
- Use project strictness settings. Prefer precise domain types and narrowing over unchecked assertions.
- Avoid unjustified `any`, broad casts, and non-null assertions. Use `unknown` at untrusted boundaries and validate it.
- Keep exported APIs small; do not leak framework or transport details through domain interfaces.
- JSDoc should explain behavior and constraints, not duplicate TypeScript signatures.
- Prefer `const`; use `let` for reassignment and `var` only when maintaining code that requires it.
- Handle rejected and intentionally detached promises. Preserve cancellation and stale-request handling where results can race.
- Use `async`/`await` or promise composition according to readability and concurrency needs.
- Avoid `eval`, `Function`, unsafe deserialization, dynamic script injection, and unsafe DOM sinks.
- Never place untrusted content into `innerHTML` or equivalent sinks without an appropriate sanitization strategy.
- Run configured type, lint, test, build, and dependency checks. Exercise success, error, loading, empty, cancellation, and race-prone states relevant to the change.

## HTML, CSS, and UI

### HTML and Accessibility

- Use valid semantic HTML with meaningful titles, heading hierarchy, and landmarks. Prefer native behavior before ARIA.
- Use buttons for actions and links for navigation; do not substitute clickable generic elements.
- Give controls programmatic labels, clear instructions, and accessible errors.
- Provide meaningful alternative text for informative images, empty alternatives for decorative images, and accessible descriptions for complex visuals.
- Meet applicable WCAG 2.2 AA criteria, including text/non-text contrast, resize/reflow, unobscured keyboard focus, minimum target size or permitted spacing, non-drag alternatives, programmatic status announcements, and accessible authentication that supports password managers and paste.
- Do not communicate essential state through color, position, hover, or motion alone.

### CSS and Responsive Design

- Use the project's design system, tokens, components, reset, and browser-support policy.
- Keep layouts usable at representative phone, tablet, and desktop widths, including zoomed text and long content.
- Respect reduced-motion and relevant platform contrast preferences.
- Keep selectors understandable and shallow. Avoid unnecessary `!important`, specificity escalation, and arbitrary z-index values.
- Prefer logical properties and resilient layouts when compatible with the support matrix.
- Define intentional loading, empty, error, disabled, selected, focus, hover, and reduced-motion states.

### UI Testing

- Test user-visible behavior rather than component internals.
- Prefer role, accessible-name, label, and visible-text queries. Use test IDs only when semantic selectors are unsuitable.
- Verify keyboard, focus, validation, error, and asynchronous states for affected workflows.
- With Playwright, prefer user-facing locators, web-first assertions, and isolated tests over brittle selectors and arbitrary sleeps.
- Visually check representative viewports when layout or styling changed. Use visual regression only when appearance is a maintained contract.
- Distinguish harness instability from product defects and rerun the complete affected flow on the final tree.

## Shell

- Use shell for small wrappers and orchestration. Move complex parsing, data structures, concurrency, or state to a more suitable language.
- Select Bash, POSIX `sh`, or another interpreter from the deployment environment; match the shebang and syntax.
- Quote expansions and preserve argument boundaries. Use arrays in Bash for argument lists.
- Prefer `$(...)` over backticks and `[[ ... ]]` for Bash-specific tests.
- Check failures deliberately. `set -e` or `set -euo pipefail` is not a complete error-handling strategy.
- Separate declaration from command substitution when exit status matters.
- Validate destructive paths as non-empty, canonical, and within an expected root before removal or overwrite.
- Use `--` before variable path arguments where supported. Use `mktemp` and traps for temporary resources when appropriate.
- Send diagnostics to stderr and useful output to stdout.
- Run ShellCheck and repository syntax or integration tests.

## Git and Production Artifacts

- Follow repository history and commit conventions; do not impose Conventional Commits or fixed subject lengths globally.
- Keep commits coherent; exclude unrelated cleanup, generated files, and formatting churn.
- Use diagrams only when they improve understanding; no diagram syntax is mandatory.
- For reusable projects, document setup, configuration, dependency checks, tests, and deployment assumptions without personal-machine coupling.
