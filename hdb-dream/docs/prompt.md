Set up a "dreaming routine" for CLaude Code -- modeled on ANthropic's dreaming feature -- so you can learn from my sessions.

1.MEMORY
If I already have a memory system (auto-memory or CLAUDE.md notes) use that. If not, create `~/.claude/memory` -- one small Markdown file per fact plus a MEMORY.md index -- and add a line to my `~.claude/CLAUDE.md` so every session reads the index.

2. The /dream skill
Create `hdb-dream/SKILL.md` so that when I type /dream, you:
- Read my session transcripts from the last 24 hours (~/.claude/projects/**/*.jsonl)
- Compare them against my memory
- Find: corrections I gave you, preferences I repeated, new facts worth keeping, memories that are now stale or wrong, duplicates
- Propose each change as a NUMBERED LIST, each with a short quote from the ranscript as evidence
- Auto-apply only tiny safe fixes (typos, index repairs). Everything else waits for me: I reply "/dream apply 1,3" or "/dream apply all"
- Never delete or rewrite a memory without my approval. If unsure, propose -- don't act.
- If you run overnight with nobody attending, write the proposals to `~/.claude/memory/dream-report.md` so I can review the proposed changes in the morning.

3. The schedule
make /dream run at 03:00 each night using whichever scheduler this computer supports (scheduled task, cron, or launchd). If nothing works, then tell me and I will launch /dream myself.

When you are done, run /dream once right now as a test and show me the proposals.

