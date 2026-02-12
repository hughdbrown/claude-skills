# claude-skills

Custom Claude Code skills derived from production software development experience. Each skill encodes patterns, conventions, and workflows learned from real projects into reusable slash commands.

## Installation

Symlink each skill directory into `~/.claude/skills/`:

```bash
ln -s /path/to/claude-skills/hdb-design ~/.claude/skills/hdb-design
ln -s /path/to/claude-skills/hdb-rust-developer ~/.claude/skills/hdb-rust-developer
ln -s /path/to/claude-skills/hdb-golang-developer ~/.claude/skills/hdb-golang-developer
```

Skills are available as slash commands in your next Claude Code session.

## Skills

### `/hdb:design` — Feature design

Design a new software feature with a PRD and detailed implementation task list. Explores the existing codebase to ground all technical decisions in the project's actual architecture. Produces two deliverables: a Product Requirements Document and a test-first task list organized by implementation stage.

### `/hdb:rust-dev` — Rust development

Develop Rust code using a batch-first workflow that minimizes compile-wait time. Writes all code before compiling, then fixes errors in a single pass. Includes build optimization reference (fast linker, sccache, workspace splitting), release profile configuration, preferred crates by domain (CLI, web, async, system, WASM, serialization, TUI, git), and Rust-specific patterns for error handling, ownership, and module organization.

### `/hdb:go-dev` — Go development

Develop Go code that compiles and passes tests on the first attempt. Front-loads type correctness and interface satisfaction to achieve green on first `go test`. Includes project infrastructure templates (directory layout, Makefile, pre-commit hooks), 8 documented Go problem areas with wrong/right examples, testing patterns (table-driven, httptest, test helpers), preferred dependency table, and conventions extracted from production Go projects.
