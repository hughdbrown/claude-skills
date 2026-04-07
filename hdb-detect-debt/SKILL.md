---
name: hdb:detect-debt
description: Detect tech debt, AI slop, and code quality issues in a codebase and produce an actionable remediation plan
---

# hdb:detect-debt

Examine a codebase through the eyes of a senior developer. Find code that doesn't understand the project, code that will rot, and code that provides false confidence. Produce a prioritized remediation plan.

## Usage

```
/detect-debt [--diff] [path]
```

- No arguments: full scan of current working directory
- `--diff`: analyze only uncommitted changes or current branch diff
- `path`: analyze a specific directory

## Instructions

When the user invokes `/detect-debt`:

### Phase 1: Understand the Project

Before looking for problems, build a mental model of how this project works.

1. **Read project structure** — use Glob to map the directory tree. Identify: source directories, test directories, config files, build files (Cargo.toml, go.mod, requirements.txt, pyproject.toml, package.json).

2. **Identify the language(s)** — determine primary and secondary languages from file extensions and build config.

3. **Read key files** — read the main entry point, 2-3 core modules, and 2-3 test files. You need to understand:
   - How does this project handle errors? (Result types, anyhow, custom errors, try/except style, Go error returns)
   - How is the project structured? (Flat, layered, domain-driven, MVC)
   - What naming conventions does it follow?
   - What dependencies does it use for common tasks (HTTP, logging, serialization, database)?
   - How are tests written? (Inline unit tests, separate test files, integration tests, mocks vs real dependencies)

4. **Check for config** — look for `.tech-debt-detector.toml` at the project root. If present, read it for exclusions, suppressions, and severity overrides.

5. **Summarize your understanding** — write a brief (5-10 line) summary of the project's conventions. This is your baseline for detecting violations.

### Phase 2: Analyze

Run mechanical checks and read code with judgment. If `tech-debt-detector` CLI is available, run it first. Otherwise, work directly.

6. **Run linters** (if available and applicable):
   - Rust: `cargo clippy --message-format=json 2>&1`
   - Python: `ruff check --output-format=json .`
   - Go: `golangci-lint run --out-format json ./...`
   - Note results but do not report linter findings directly — use them as signals for deeper analysis.

7. **Run tech-debt-detector CLI** (if installed):
   ```bash
   tech-debt-detector --project . --format json
   ```
   Or for diff mode:
   ```bash
   tech-debt-detector --project . --diff --format json
   ```

8. **If CLI is not available, analyze directly.** Read source files and look through the three lenses:

   **Lens 1 — Code that doesn't understand the project:**
   - Does new/changed code follow the project's established error handling pattern?
   - Does it respect module boundaries and architectural structure?
   - Does it use the same libraries the project already uses for the same tasks?
   - Does it follow the project's naming conventions?
   - Does it call APIs that exist in the dependency versions specified?

   **Lens 2 — Code that will rot:**
   - Are errors being swallowed or caught-and-ignored?
   - Are resources opened without cleanup?
   - Is there duplicated logic that should use existing utilities?
   - Is code more complex than the problem requires?
   - Are there unbounded collections, missing timeouts, or absent cancellation?

   **Lens 3 — Code that provides false confidence:**
   - Do tests actually assert on behavior, or just exercise code?
   - Are error paths tested, or only the happy path?
   - Is input validation checking the things that matter?
   - Are error messages specific enough to debug with?

9. **For diff mode** — focus analysis on changed files only, but compare against the project's established patterns from Phase 1. Flag changes that introduce inconsistency.

### Phase 3: Report Findings and Remediation Plan

10. **Format each finding** using this structure:

```
CATEGORY: Doesn't Understand the Project | Will Rot | False Confidence
SEVERITY: must-fix | should-fix | consider
URGENCY: high | moderate | low
FILE: path/to/file.rs:42-58
WHAT: One sentence describing the problem
WHY: Why this matters — what breaks, what debt it introduces, or what convention it violates
EVIDENCE: The specific code or pattern that triggered the finding
FIX: Concrete recommendation — what to change, with example code when appropriate
```

Determine urgency based on how central the affected code is:
- **high** — hot path, shared abstraction, or high fan-in module
- **moderate** — active but not central code
- **low** — isolated, rarely touched, leaf module

11. **Order findings** — sort by: must-fix first, then by urgency (high before low), then by category (doesn't understand > will rot > false confidence).

12. **Present the remediation plan** — group related findings that should be fixed together. For each group:
    - Explain the root cause connecting the findings
    - Provide a concrete fix with code examples
    - Note any dependencies between fixes (e.g., "fix the error type first, then update the handlers")

13. **Do NOT report:**
    - Findings that linters already surface well (formatting, unused variables) unless they indicate deeper issues
    - Generic advice without pointing to specific code
    - Style preferences that aren't established project conventions
    - Complexity metrics without explaining why the complexity is problematic in this specific context

### Phase 4: Follow-up

14. **Offer to fix** — after presenting findings, offer to implement the fixes. If the user agrees, work through the remediation plan in order, committing each logical unit separately.
