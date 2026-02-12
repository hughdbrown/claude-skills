# claude-skills

Custom Claude Code skills derived from production software development experience. Each skill encodes patterns, conventions, and workflows learned from real projects into reusable slash commands.

## Installation

### Using GNU stow (recommended)

[GNU stow](https://www.gnu.org/software/stow/) is a symlink manager that creates and maintains symlinks from a target directory into a package directory. It keeps this repo as the single source of truth — adding, updating, or removing skills requires no manual symlink management.

Install stow:

```bash
# macOS
brew install stow

# Debian/Ubuntu
sudo apt install stow

# Fedora
sudo dnf install stow
```

Ensure the target directory exists:

```bash
mkdir -p ~/.claude/skills
```

Deploy all skills by running stow from the parent directory of this repo, with `~/.claude/skills/` as the target:

```bash
cd /path/to/parent-of-this-repo
stow -t ~/.claude/skills --ignore='README\.md' claude-skills
```

For example, if this repo is cloned to `~/workspace/claude-skills`:

```bash
cd ~/workspace
stow -t ~/.claude/skills --ignore='README\.md' claude-skills
```

This creates symlinks for each skill directory:

```
~/.claude/skills/hdb-design/         -> ~/workspace/claude-skills/hdb-design/
~/.claude/skills/hdb-rust-developer/ -> ~/workspace/claude-skills/hdb-rust-developer/
~/.claude/skills/hdb-golang-developer/ -> ~/workspace/claude-skills/hdb-golang-developer/
```

**After adding new skills** to the repo, restow to pick up the changes:

```bash
cd ~/workspace
stow -R -t ~/.claude/skills --ignore='README\.md' claude-skills
```

**To remove all symlinks** (uninstall):

```bash
cd ~/workspace
stow -D -t ~/.claude/skills claude-skills
```

**How stow works here:** Stow treats the repo directory (`claude-skills`) as a "package" whose internal directory structure mirrors the target (`~/.claude/skills/`). Each subdirectory in the repo becomes a symlinked subdirectory in the target. The `--ignore` flag prevents non-skill files like `README.md` from being linked. Stow automatically ignores `.git` directories.

### Manual symlinks

If you prefer not to install stow, symlink each skill directory individually:

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
