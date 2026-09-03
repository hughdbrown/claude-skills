# scripts/ — deterministic gates and round orchestration

All uv/PEP-723 single files: `./name.py` (or `uv run --script name.py`) fetches
its declared deps (`click`, `markdown-it-py`, `mdit-py-plugins`; `sympy` for the
answer-check template). Run from the book root. None of them edits the book;
run-review.py and qwen-resolve.py write under `docs/reviews/`.

**Markup is parsed, never regex-scanned.** `mdprose.py` turns each file into
prose blocks with line numbers via markdown-it-py + the dollarmath plugin (code
fences, `$$` blocks, inline math and code, admonish wrappers all become tokens);
TOML goes through `tomllib`; the manifest is JSON. Regexes appear only where the
input is natural language (a phrase list, a sentence split, a quotation).
Argument parsing is `click` throughout.

| Script | What it gates | Exit 1 when |
|---|---|---|
| `slop-scan.py` | AI-slop phrases (`slop-phrases.txt`: blocking / soft / note tiers) and em-dash density in `src/` + `staging/` prose | any blocking phrase, or ≥3 soft tics in one file |
| `self-echo.py` | distinctive sentences repeated across files or near-duplicated (5-gram Jaccard) | an exact cross-file repeat |
| `pacing-audit.py` | per-day words / examples / exercises vs the book's median day; Gentle-stretch and Stuck? presence when most days have them | a day > 1.3x the median, or off the exercise band |
| `plagiarism-sample.py` | picks the most distinctive sentences per file and lists every long quotation, as a WebSearch checklist | never (it produces work, not a verdict) |
| `run-review.py --round N` | snapshot + feature detection + scans + `manifest.json`/`.md` + `contract.md` | no `src/dayNN.md` |
| `aggregate-review.py --round N` | parses each report's Verdict heading and finding bullets into `summary.md`; blocking per `manifest.json`; missing report = CHANGES_REQUIRED | not APPROVED |
| `answer-check-template.py` | copied per chunk into `docs/reviews/round-N/checks/`; sympy limit/value/solve/simplify/series/matrix checks | any FAIL |
| `qwen-resolve.py dayNN...` | blind re-solve of each exercise on the LAN model; leads only | never; silently skips when the host is down |
| `roster.toml` | the policy: lens → chunk, model, blocking, condition, brief | — |
| `mdprose.py` | shared Markdown parser (not a command) | — |

## Tuning

- Add a phrase: edit `slop-phrases.txt` under the right tier. Per-book
  additions go in the book's `docs/slop-phrases.txt` and `--phrases`.
- A book whose exercises heading does not start with "Try it": pass
  `--exercise-heading Exercises` to `pacing-audit.py` and `qwen-resolve.py`.
- A book whose exemplar is not the median day: `pacing-audit.py --exemplar day03`.
- LAN model host/model: `--lan-host` on run-review, `--host/--model` on qwen-resolve.

## Negative tests (do these once per new book before trusting a gate)

A gate that has never failed is not a gate. Plant one defect of each kind and
confirm the exit code: a forbidden phrase in a day (`slop-scan`), a sentence
pasted from Day 2 into the afterword (`self-echo`), a wrong `claimed` in a
checks file (`answer-check`), a day with double the exercises (`pacing-audit`).
