---
name: hdb-dream
description: Nightly "dreaming" review of Claude Code sessions — read the last 24 hours of transcripts, compare them against auto-memory, and propose memory adds/updates/deletions as a numbered, evidence-quoted list. Use when the user types /dream or /dream apply, or when run unattended on a schedule (writes proposals to ~/.claude/dream-report.md).
---

# hdb-dream

Learn from recent sessions the way Anthropic's "dreaming" feature does: review
what happened, compare it to what memory already says, and propose changes.
Memory lives in the existing auto-memory system: one file per fact plus a
`MEMORY.md` index under `~/.claude/projects/<project>/memory/`.

## Usage

```
/dream                 # review last 24h, propose numbered changes
/dream apply 1,3       # apply proposals 1 and 3 from the latest report
/dream apply all       # apply every pending proposal
/dream --hours 48      # widen the review window
```

## /dream — propose

1. **Extract transcripts.** Run:
   ```
   ~/.claude/skills/hdb-dream/scripts/extract_transcripts.py --hours 24
   ```
   It prints a digest of user messages (and session summaries) from every
   `~/.claude/projects/**/*.jsonl` touched in the window, grouped by project.
   Skip any session belonging to the currently running /dream itself.

2. **Load the matching memory.** For each project with activity, read
   `~/.claude/projects/<project>/memory/MEMORY.md` and the memory files it
   indexes. If a project has no memory dir, note that; do not create one.

3. **Compare.** Look specifically for:
   - **Corrections** the user gave ("no, don't...", "I told you...", reverted work)
   - **Preferences repeated** across sessions (tools, style, workflow habits)
   - **New durable facts** worth keeping (type: user/feedback/project/reference)
   - **Stale or wrong memories** contradicted by recent transcripts
   - **Duplicates** — two memory files covering the same fact

4. **Propose as a NUMBERED LIST.** Every proposal has:
   - Action: `ADD` / `UPDATE` / `DELETE` / `MERGE`, target project + memory file
   - One line saying exactly what would change
   - Evidence: a short direct quote from the transcript, with the session
     `.jsonl` path so it can be checked

5. **Auto-apply only tiny safe fixes**, and say so in the output:
   - typo fixes inside an existing memory file
   - `MEMORY.md` index repairs (missing line for an existing file, or a line
     pointing at a file that exists under a different name)
   Everything else waits for approval.

6. **Write the report.** Always write the numbered proposals to
   `~/.claude/dream-report.md` (date-stamped, overwriting the previous report)
   so an unattended overnight run leaves something to review in the morning.
   If a user is present, also show the list in the conversation and stop —
   do not apply anything beyond step 5.

## /dream apply — act on approvals

1. Read `~/.claude/dream-report.md` (or the proposal list from this
   conversation if it is more recent).
2. Apply only the numbered items the user named. Follow auto-memory
   conventions: frontmatter (`name`, `description`, `metadata.type`), one fact
   per file, `[[links]]`, and a one-line pointer in that project's `MEMORY.md`.
3. Mark applied items in `dream-report.md` (`[applied 2026-08-03]`) and report
   what was done.

## Guardrails (rigid — do not adapt away)

- **Never delete or rewrite a memory without approval.** If unsure whether
  something qualifies as a tiny safe fix, propose it — don't act.
- Quotes in evidence must be verbatim from the transcript, never paraphrased.
- Don't store what the repo/git history already records, or one-off session
  trivia; durable facts only.
- Transcripts may contain sensitive content (legal, personal). Quote the
  minimum needed as evidence.
