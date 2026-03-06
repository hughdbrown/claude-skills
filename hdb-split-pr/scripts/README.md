# splitpr

Decompose oversize git branches into focused, dependency-ordered pull requests.

Two command-line tools share a SQLite database as their contract:

- **`splitpr_00`** — Analyzes a branch and produces a partition plan (the database)
- **`splitpr_05`** — Reads the database and executes the plan (creates branches, pushes, opens PRs)

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- `ANTHROPIC_API_KEY` environment variable
- `gh` CLI (optional, for PR creation in splitpr_05)

## Installation

```bash
cd scripts
uv run splitpr_00 --help
```

`uv` installs dependencies (`click`, `anthropic`) automatically on first run.

## Usage

### Step 1: Analyze the branch

```bash
# From the repo with the oversize branch checked out:
uv run --project /path/to/scripts splitpr_00 --base main -v
```

This produces:
- `splitpr_00.db` — SQLite database with the full analysis
- `splitpr_00-report.md` — Human-readable markdown summary

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--base, -b` | auto-detect | Base branch to diff against |
| `--db-path, -d` | `splitpr_00.db` | SQLite output path |
| `--report, -r` | `splitpr_00-report.md` | Markdown report path |
| `--model, -m` | `claude-sonnet-4-20250514` | Anthropic model |
| `--phase` | all (1-5) | Stop after this phase |
| `--force` | off | Analyze even if branch is small |
| `--verbose, -v` | off | Detailed progress output |

### Step 2: Review the plan

Read `splitpr_00-report.md` or query the database directly:

```bash
sqlite3 splitpr_00.db "SELECT pr_id, branch_name, merge_order, file_count FROM prs ORDER BY merge_order"
```

### Step 3: Execute the plan

```bash
uv run --project /path/to/scripts splitpr_05 --database splitpr_00.db -v
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--database, -d` | (required) | Path to splitpr_00 database |
| `--dry-run, -n` | off | Preview without creating branches |
| `--model, -m` | `claude-sonnet-4-20250514` | Model for PR descriptions |
| `--verbose, -v` | off | Detailed progress output |

## Architecture

```
scripts/
├── pyproject.toml
├── splitpr_common/          # Shared read-only git primitives
│   └── git_ops.py
├── splitpr_00/              # Analysis & planning (phases 1-5)
│   ├── cli.py               #   CLI entry point
│   ├── db.py                #   SQLite schema + helpers
│   ├── models.py            #   Dataclasses
│   ├── git_ops.py           #   Git read operations
│   ├── ai.py                #   Claude tool_use integration
│   ├── inventory.py         #   Phase 1: commits, themes, cross-cutting files
│   ├── dependencies.py      #   Phase 2: DAG, cycle detection, merge ordering
│   ├── partition.py         #   Phase 3: file-to-PR assignment
│   ├── tasks.py             #   Phase 4: per-PR task generation
│   └── report.py            #   Phase 5: markdown report
├── splitpr_05/              # Execution engine
│   ├── cli.py               #   CLI entry point
│   ├── db.py                #   Database reader
│   ├── models.py            #   Dataclasses
│   ├── git_ops.py           #   Git write operations (branch, cherry-pick, push)
│   ├── ai.py                #   PR description generation
│   └── executor.py          #   Execution pipeline
└── tests/
    └── test_validate_preconditions.py
```

## Analysis Phases (splitpr_00)

| Phase | Module | What it does | AI calls |
|-------|--------|--------------|----------|
| 1 | `inventory.py` | List commits, classify into themes, find cross-cutting files | 1 (batched) |
| 2 | `dependencies.py` | Build dependency DAG, detect cycles, compute merge order | 1-2 |
| 3 | `partition.py` | Assign every file to exactly one PR, verify completeness | 1 |
| 4 | `tasks.py` | Generate ordered tasks with recovery commands per PR | 1 per PR |
| 5 | `report.py` | Write markdown summary | 0 |

Total: ~6-10 AI calls (batched, not per-commit).

## Database Schema

The SQLite database is the complete handoff artifact between the two tools. The executor never re-queries git history or makes AI calls for planning.

### Tables

| Table | Rows represent | Key columns |
|-------|---------------|-------------|
| `run_metadata` | Key-value run context | source_branch, base_branch, merge_base_sha, head_rev, repo_toplevel |
| `commits` | Every commit on the branch | sha, ordinal, subject, body, author, date, insertions, deletions |
| `commit_files` | Per-commit file changes | sha, file_path, status (A/M/D/R), old_path, insertions, deletions |
| `changed_files` | All files changed vs base | file_path, status, insertions, deletions |
| `themes` | Theme groupings | theme_id, name, description, commit_count, file_count, net_lines |
| `commit_themes` | Commit-to-theme mapping | sha, theme_id, confidence |
| `cross_cutting_files` | Files touched by multiple themes | file_path, theme_id, commit_count |
| `prs` | Planned pull requests | pr_id, branch_name, title, merge_order, base_branch, file_count |
| `pr_dependencies` | DAG edges | pr_id, depends_on, reason |
| `file_assignments` | The partition table | file_path, pr_id, strategy, ai_reasoning |
| `cherry_pick_candidates` | Commits per PR | pr_id, sha, is_clean |
| `tasks` | Ordered task list per PR | task_id, pr_id, ordinal, subject, description, acceptance, recovery_cmds |

### How splitpr_05 uses the database

1. `run_metadata` — source branch, base branch, HEAD rev for precondition checks
2. `prs` (ordered by `merge_order`) — branch creation order and `git checkout -b` targets
3. `prs.base_branch` — what to fork each branch from
4. `cherry_pick_candidates` (where `is_clean = true`) — commits to cherry-pick
5. `file_assignments` — files to `git checkout` per PR
6. `pr_dependencies` — dependency links for PR descriptions
7. `tasks` — execution checklist

## Tests

```bash
uv run --project /path/to/scripts pytest tests/ -v
```
