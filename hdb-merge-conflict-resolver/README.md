# hdb:merge-conflict-resolver

AI-assisted git merge conflict resolver. Analyzes each conflict block with Claude and applies the correct resolution strategy.

## What it does

When a `git merge`, `git rebase`, or `git cherry-pick` produces conflicts, this skill:

1. Discovers all conflicted files and detects the operation type
2. Parses conflict markers (standard 2-way and diff3 3-way)
3. Sends each conflict block with surrounding context to Claude for analysis
4. Applies one of four resolution strategies:
   - **take_ours** — keep the current branch's changes
   - **take_theirs** — keep the incoming branch's changes
   - **take_both** — incorporate both sides (e.g., additive imports)
   - **custom** — AI-crafted merge when changes genuinely overlap
5. Logs every decision with reasoning to a SQLite database for auditability
6. Stages resolved files with `git add`

## Skill usage

```
/hdb:merge-conflict-resolver [--dry-run] [--model <model>]
```

See [SKILL.md](SKILL.md) for the full skill definition with phases, resolution patterns, and pitfall documentation.

## Automation script

A standalone Python CLI at `scripts/mergefix/` automates conflict resolution outside of Claude Code.

### Prerequisites

- Python 3.11+
- `ANTHROPIC_API_KEY` environment variable (optional — without it, all conflicts default to `take_theirs`)

### Installation

```bash
cd scripts
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Usage

```bash
# Preview all resolutions without modifying files
python -m mergefix --dry-run

# Resolve all conflicts and stage files
python -m mergefix

# Use a specific model
python -m mergefix --model claude-sonnet-4-20250514

# Custom database path for audit log
python -m mergefix --database /tmp/mergefix.db

# Verbose output with per-block reasoning
python -m mergefix --dry-run --verbose
```

### CLI options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--dry-run` | `-n` | off | Show proposed resolutions without applying |
| `--model` | `-m` | `claude-sonnet-4-20250514` | Anthropic model for analysis |
| `--database` | `-d` | `.git/mergefix.db` | SQLite database for logging |
| `--verbose` | `-v` | off | Print per-block reasoning |
| `--version` | | | Show version |

### Module structure

| Module | Purpose |
|--------|---------|
| `cli.py` | Click CLI, logging setup, summary output |
| `git_ops.py` | All git commands via `subprocess` |
| `ai.py` | Anthropic SDK — structured tool_use for conflict analysis |
| `db.py` | SQLite schema and helpers for audit trail |
| `models.py` | Shared dataclasses (`ConflictBlock`, `Resolution`, `Strategy`, etc.) |
| `resolver.py` | Core engine — conflict parsing, AI coordination, file rewriting |
| `__main__.py` | Entry point for `python -m mergefix` |

### Confidence thresholds

| Confidence | Behavior |
|-----------|----------|
| >= 0.9 | Auto-apply |
| 0.7 - 0.9 | Apply but flag for review |
| < 0.7 | Skip auto-apply — requires manual resolution |

### Automatically skipped files

Lock files (`package-lock.json`, `Cargo.lock`, `yarn.lock`, etc.), binary files, and delete/modify conflicts are skipped with a logged reason. These require manual resolution or regeneration after the merge.

### Rebase note

During `git rebase`, "ours" and "theirs" are swapped relative to `git merge`:
- **Merge:** ours = current branch, theirs = incoming
- **Rebase:** ours = upstream (the branch being rebased onto), theirs = your commit being replayed

The tool detects the operation type and labels accordingly.
