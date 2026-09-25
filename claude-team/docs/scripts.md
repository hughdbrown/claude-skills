# Scripts

All scripts are self-contained `uv run --script` files (Python ≥ 3.10, `click`). They share
`scripts/taskcard.py` for parsing cards and handoffs. Run them from the target repo root.
They default to `tasks/` and `handoffs/`.

| Script | Purpose | Exit codes |
|---|---|---|
| `new_task.py TITLE [--model] [--allow]... [--forbid]... [--verify]... [--depends-on]... [--read-only]` | Create the next `tasks/TASK-###-slug.md` from the template | 0 / 1 on collision |
| `render_worker_prompt.py CARD [--json]` | Build the worker prompt and `Agent` settings from a card | 0 / 1 if no model |
| `check_scope.py CARD (--commit SHA \| --range A...B \| --worktree DIR [--base main])` | Flag changed files that are forbidden or not on the allowed list | 0 in scope, 1 violations, 2 usage |
| `validate_handoff.py HANDOFF [--task CARD] [--repo DIR] [--no-git]` | Reject handoffs without evidence | 0 / 1 |
| `progress.py show [--write PROGRESS.md]` | Status table from cards, handoffs, and decisions | 0 |
| `progress.py ready` | Cards whose dependencies are accepted and that have no handoff yet | 0 |
| `progress.py set TASK-### accepted\|rejected\|escalated\|in-progress\|cancelled [--note]` | Record a coordinator decision in `tasks/status.json` | 0 / 1 unknown task |
| `session_cost.py [--session ID \| --transcript FILE] [--json]` | Tokens and cost by model and by agent | 0 |

## Card format the scripts rely on

- The first line is `# TASK-###: Title`.
- `## Assigned Model` mentions opus, sonnet, or haiku.
- `## Depends On` lists `TASK-###` IDs, or says None.
- In `## Scope`, `Allowed files:` and `Do not modify:` are followed by bullet lists.
  Backticked entries are enforced as paths. A trailing `/` means a directory prefix, and
  `*`, `?`, and `[` are globs. Prose entries are shown to the reviewer but not enforced.
- `## Verification` has a fenced block with one command per line. `validate_handoff.py
  --task` requires each command to appear in the handoff's output.

## Full cycle

```bash
S=~/workspace/hughdbrown/claude-skills/claude-team/scripts
$S/new_task.py "Map auth checks" --model haiku --read-only
$S/new_task.py "List endpoint" --model sonnet --allow src/api/list.ts --allow src/api/list.test.ts \
    --forbid src/auth/ --verify "pnpm test src/api/list.test.ts" --depends-on TASK-001
$S/render_worker_prompt.py tasks/TASK-001-*.md --json      # → Agent(...)
$S/progress.py set TASK-001 accepted --note "findings used for contract"
$S/progress.py ready                                       # → TASK-002
$S/render_worker_prompt.py tasks/TASK-002-*.md --json      # → Agent(..., isolation: worktree)
$S/check_scope.py tasks/TASK-002-*.md --commit <sha> --repo <worktree>
$S/validate_handoff.py handoffs/TASK-002.md --task tasks/TASK-002-*.md --repo <worktree>
$S/progress.py set TASK-002 accepted --note "cherry-picked"
$S/progress.py show --write PROGRESS.md
$S/session_cost.py
```
