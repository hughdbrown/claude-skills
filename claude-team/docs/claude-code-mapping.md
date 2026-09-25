# Mapping the team onto Claude Code

| Concept in the workflow | Claude Code mechanism |
|---|---|
| Opus coordinator | The main session (run it on Opus 5.5) |
| Sonnet worker | `Agent` tool, `model: "sonnet"`, `subagent_type: "general-purpose"` |
| Haiku read-only scout | `Agent` tool, `model: "haiku"`, `subagent_type: "Explore"`; Explore's tools are read-only, which enforces "do not modify code" |
| Haiku code-writing worker | `Agent` tool, `model: "haiku"`, `subagent_type: "general-purpose"` |
| One worktree per coding worker | `isolation: "worktree"` on the `Agent` call (auto-cleaned if unchanged) |
| Parallel dispatch | Several `Agent` calls in one assistant message |
| Worker completion | Background notification. Don't poll; don't predict results |
| Follow-up correction to the same worker | `SendMessage` to the agent's name or ID, which keeps its context |
| Large fan-outs | `Workflow` tool, **only** if the user explicitly asks for multi-agent orchestration |

`scripts/render_worker_prompt.py <card> --json` emits `description`, `subagent_type`,
`model`, `isolation`, and `prompt`, ready to pass to `Agent`.

## Finding the worker's commit

With `isolation: "worktree"`, the worker commits on a branch in its own worktree. The
worker's handoff gives the SHA, and the `Agent` result reports the worktree path. Point
`check_scope.py --commit <sha> --repo <worktree>` and `validate_handoff.py --repo <worktree>`
at that path, then `git cherry-pick <sha>` into your integration branch. The worktrees share
the repository's object store, so the SHA is visible from the main checkout as well.

## Handoff files from read-only workers

Explore agents can't write files. The Haiku template tells them to return the handoff in
their reply. Save it to `handoffs/TASK-###.md` yourself so `progress.py` sees it.

## Outside Claude Code

The same artifacts work with separate `claude -p --model sonnet` processes, each started in
its own worktree (`git worktree add ../proj-task-042 -b agent/task-042`) with the rendered
prompt on stdin.
