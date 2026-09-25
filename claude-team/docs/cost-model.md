# Cost model

## Prices

These are the public API-equivalent prices from `PROMPT.md`, stored in
`resources/pricing.json` (edit that file when they change):

| Model | Input $/1M | Output $/1M | vs Haiku | vs Sonnet |
|---|---:|---:|---:|---:|
| Haiku 4.5 | 1 | 5 | 1× | 0.5× |
| Sonnet 5 | 2 | 10 | 2× | 1× |
| Opus 5.5 | 4 | 20 | 4× | 2× |

Cache writes are billed at a multiple of the input price (1.25× for 5-minute, 2× for 1-hour
entries), and cache reads at 0.1×. In long agent sessions, cache reads are usually most of
the input volume, so the exact multipliers matter less than which tier carries the volume.

## The equation

```
Total = Opus planning + Sonnet implementation + Haiku support + Opus review/integration + rework
```

Two terms matter most:

- **Rework.** Every rejected handoff costs the worker's tokens again, plus Opus review
  tokens again. Well-specified cards reduce it more than cheaper models do.
- **Opus review.** It grows with diff size and with how much of the diff Opus has to
  re-derive. Focused commits and good handoffs keep it small.

## What drives cost up

- Context: repo content and tool results fed to each agent (a reason to keep worker context narrow)
- Output: reasoning, code, reports
- Tool-call loops, and failed or repeated attempts
- Integration repair of output that fails at merge time

## Measuring a run

```bash
scripts/session_cost.py                     # newest session for this directory
scripts/session_cost.py --session <id>      # a specific session
scripts/session_cost.py --json
```

This script reads the main transcript and each `subagents/agent-*.jsonl`, dedupes usage by
request ID, and prices the tokens by model. It then prices the same tokens at the baseline
(Opus) rate. That comparison is only a rough indicator, since an all-Opus run would not
have used exactly the same tokens. Still, if the "saved" number is near 0%, the
coordinator did the implementation itself.

Models missing from `pricing.json` are reported as unpriced and left out of both sides of
the comparison. The script doesn't guess their prices.
