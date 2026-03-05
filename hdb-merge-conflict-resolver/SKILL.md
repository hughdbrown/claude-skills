---
name: hdb:merge-conflict-resolver
description: Resolve git merge conflicts using AI-assisted analysis to choose ours, theirs, both, or a custom resolution
---

# hdb:merge-conflict-resolver

Resolve git merge conflicts by analyzing each conflict block and determining the correct resolution strategy using AI-assisted decision-making.

## Usage

```
/hdb:merge-conflict-resolver [--dry-run] [--model <model>]
```

## IMPORTANT

This skill operates on a repository with unresolved merge conflicts (i.e., after a failed `git merge`, `git rebase`, `git cherry-pick`, or `git stash pop`). It parses conflict markers, sends each conflict to an AI model with surrounding context, and applies the chosen resolution. Every decision is logged to a SQLite database for auditability.

## Description

When a git merge, rebase, or cherry-pick produces conflicts, this skill:

1. Discovers all files with conflict markers
2. Parses each conflict block (extracting the "ours" and "theirs" sides, plus any common ancestor in diff3 mode)
3. Gathers surrounding file context and commit history for each conflict
4. Sends each conflict to Claude for analysis
5. Applies one of four resolution strategies:
   - **take_ours** — keep the changes from the current branch (HEAD)
   - **take_theirs** — keep the changes from the incoming branch
   - **take_both** — incorporate changes from both sides (ordered appropriately)
   - **custom** — a manually crafted resolution when neither side is sufficient alone
6. Logs every decision with reasoning to a SQLite database
7. Marks resolved files with `git add`

The most common resolutions are `take_ours` and `take_theirs` (simple side selection). `take_both` is common for additive changes like imports or list entries. `custom` is the rarest, used when changes genuinely overlap and require careful merging.

## Instructions

When the user invokes `/hdb:merge-conflict-resolver [--dry-run] [--model <model>]`:

### Phase 1: Discover Conflicts

1. **Verify the repository is in a conflicted state.** Run:

   ```bash
   git status --porcelain
   ```

   Look for lines starting with `UU`, `AA`, `DD`, `AU`, `UA`, `DU`, `UD` — these indicate unmerged paths. If no conflicts exist, inform the user and stop.

2. **Identify the merge operation in progress.** Determine whether this is a merge, rebase, or cherry-pick by checking:

   ```bash
   # Check for merge in progress
   test -f .git/MERGE_HEAD && echo "merge"

   # Check for rebase in progress
   test -d .git/rebase-merge -o -d .git/rebase-apply && echo "rebase"

   # Check for cherry-pick in progress
   test -f .git/CHERRY_PICK_HEAD && echo "cherry-pick"
   ```

3. **List all conflicted files:**

   ```bash
   git diff --name-only --diff-filter=U
   ```

4. **Gather merge context.** Identify what is being merged:

   ```bash
   # For a merge: what branch is being merged in
   git log --oneline -1 MERGE_HEAD 2>/dev/null

   # Current branch
   git rev-parse --abbrev-ref HEAD

   # Recent commits on both sides
   git log --oneline -5 HEAD
   git log --oneline -5 MERGE_HEAD 2>/dev/null
   ```

5. **Present a summary to the user:**

   ```
   Merge conflict detected: merge of 'feature-branch' into 'main'
   Conflicted files: 7

   1. src/auth/login.py (3 conflict blocks)
   2. src/api/routes.py (1 conflict block)
   3. tests/test_auth.py (2 conflict blocks)
   ...
   ```

### Phase 2: Parse Conflicts

6. **For each conflicted file, parse the conflict markers.** Standard conflict markers look like:

   ```
   <<<<<<< HEAD
   (ours — current branch content)
   =======
   (theirs — incoming branch content)
   >>>>>>> branch-name
   ```

   In diff3 mode (recommended), there is also a common ancestor:

   ```
   <<<<<<< HEAD
   (ours — current branch content)
   ||||||| merged common ancestors
   (base — common ancestor content)
   =======
   (theirs — incoming branch content)
   >>>>>>> branch-name
   ```

7. **Extract context around each conflict block.** Include 10-20 lines before and after the conflict markers to give the AI enough context to understand the purpose of the code.

8. **Build a conflict inventory:**

   | File | Block | Ours Lines | Theirs Lines | Has Base | Complexity |
   |------|-------|-----------|-------------|----------|------------|
   | src/auth/login.py | 1/3 | 5 | 8 | yes | medium |
   | src/auth/login.py | 2/3 | 2 | 2 | yes | low |
   | src/api/routes.py | 1/1 | 12 | 15 | no | high |

### Phase 3: Analyze and Resolve

9. **For each conflict block, send it to Claude for analysis.** The prompt should include:
   - The conflict block (ours, base if available, theirs)
   - Surrounding file context (before and after the conflict)
   - The file path and language
   - The merge operation type (merge/rebase/cherry-pick)
   - The branch names involved
   - Recent commit messages from both sides

10. **Claude determines the resolution strategy.** The AI returns a structured response:

    ```json
    {
      "strategy": "take_ours | take_theirs | take_both | custom",
      "resolved_content": "the actual resolved code",
      "confidence": 0.95,
      "reasoning": "explanation of why this resolution is correct"
    }
    ```

    **Decision criteria:**

    | Strategy | When Used | Example |
    |----------|-----------|---------|
    | `take_ours` | The current branch's changes are correct and complete; the incoming changes are superseded or irrelevant | Ours refactored the function; theirs still uses the old API |
    | `take_theirs` | The incoming changes are correct and complete; the current branch's changes should be discarded | Theirs fixed a bug; ours has the buggy version |
    | `take_both` | Both sides added non-overlapping content that should coexist | Both sides added new imports, new test cases, or new list entries |
    | `custom` | The changes genuinely overlap and require intelligent merging | Both sides modified the same function differently; the result needs elements from each |

11. **Apply confidence thresholds:**

    | Confidence | Action |
    |-----------|--------|
    | >= 0.9 | Auto-apply the resolution |
    | 0.7 - 0.9 | Apply but flag for review |
    | < 0.7 | Present to user for manual confirmation |

    In `--dry-run` mode, all resolutions are presented without applying.

### Phase 4: Apply Resolutions

12. **For each resolved conflict, apply the resolution:**
    - Replace the conflict block (including markers) with the resolved content
    - Preserve the rest of the file exactly as-is

13. **Stage resolved files:**

    ```bash
    git add <resolved-file>
    ```

14. **Handle special cases:**

    | Case | Resolution |
    |------|-----------|
    | Both sides deleted the file | `git rm <file>` |
    | One side deleted, other modified | Present to user — cannot auto-resolve |
    | Binary file conflict | Present to user — cannot auto-resolve |
    | File added on both sides with different content | Treat as a single conflict block |

15. **Verify each resolved file compiles/parses** (language-dependent):

    ```bash
    # Python
    python -m py_compile <file>

    # Go
    gofmt -e <file>

    # Rust
    # (skip — requires full build context)

    # JSON/YAML
    python -c "import json; json.load(open('<file>'))"
    ```

### Phase 5: Report

16. **Log all decisions to the SQLite database.** Each resolution record includes:
    - File path
    - Conflict block number
    - Strategy chosen
    - Confidence score
    - AI reasoning
    - The ours/theirs/base/resolved content
    - Timestamp

17. **Present a resolution summary:**

    ```
    Merge Conflict Resolution Summary
    ══════════════════════════════════
    Operation: merge of 'feature-branch' into 'main'
    Total conflicts: 12 across 7 files

    Resolutions:
      take_ours:   4 (33%)
      take_theirs: 3 (25%)
      take_both:   4 (33%)
      custom:      1 (8%)

    Confidence:
      High (>= 0.9): 10
      Medium (0.7-0.9): 2
      Low (< 0.7): 0

    Status:
      Applied: 12
      Flagged for review: 2
      Manual required: 0

    All files staged. Run 'git commit' to complete the merge.
    ```

18. **If `--dry-run` was specified**, present all resolutions without applying them. Include the proposed resolved content for each conflict.

---

## Conflict Parsing Details

### Standard markers

```
<<<<<<< HEAD
current branch content
=======
incoming branch content
>>>>>>> branch-name-or-sha
```

### Diff3 markers

```
<<<<<<< HEAD
current branch content
||||||| merged common ancestors
common ancestor content
=======
incoming branch content
>>>>>>> branch-name-or-sha
```

The diff3 format is strongly preferred because the common ancestor reveals what both sides changed relative to the original, making the resolution more accurate.

**Recommend enabling diff3:**
```bash
git config merge.conflictstyle diff3
```

---

## Resolution Patterns

### Pattern: Additive imports (take_both)

Both sides added different imports:
```python
<<<<<<< HEAD
import redis
import celery
=======
import boto3
import requests
>>>>>>> feature
```
Resolution: include all four imports, sorted.

### Pattern: Configuration value change (take_theirs)

```python
<<<<<<< HEAD
MAX_RETRIES = 3
=======
MAX_RETRIES = 5  # increased for production stability
>>>>>>> hotfix
```
Resolution: take the intentional change (theirs), which has a comment explaining the reason.

### Pattern: Function refactor vs. bug fix (custom)

```python
<<<<<<< HEAD
def process(data):
    result = transform(data)
    return validate(result)
=======
def process(data):
    if not data:
        return None  # bug fix: handle empty input
    result = old_transform(data)
    return result
>>>>>>> bugfix
```
Resolution: combine the bug fix (null check) with the refactored code:
```python
def process(data):
    if not data:
        return None
    result = transform(data)
    return validate(result)
```

### Pattern: Deleted vs. modified (manual)

One side deleted a function, the other modified it. This requires understanding whether the deletion was intentional (dead code removal) or accidental. Present to the user.

---

## Common Pitfalls

### 1. Conflict inside string literals or comments

The AI must recognize that conflict markers inside strings or comments are actual git conflict markers, not content. Always check for the `<<<<<<<`, `=======`, `>>>>>>>` pattern at the start of lines.

### 2. Nested conflicts

Rarely, a conflict block can span another area that was also modified. The parser must handle the outermost markers first.

### 3. Whitespace-only conflicts

Formatting changes (indentation, trailing whitespace) on both sides. Resolution: prefer whichever side matches the project's formatter output. If unknown, take theirs (the incoming change).

### 4. Lock file conflicts (package-lock.json, Cargo.lock, etc.)

Never attempt to merge lock files by content. Instead:
```bash
git checkout --theirs package-lock.json
npm install  # regenerate from package.json
git add package-lock.json
```

### 5. Migration file conflicts

Database migration files should never be merged by content. Flag for manual resolution.

### 6. Resolving during rebase vs. merge

During rebase, "ours" and "theirs" are swapped relative to merge:
- **Merge:** ours = current branch, theirs = incoming branch
- **Rebase:** ours = the branch being rebased onto (upstream), theirs = the commit being replayed (your changes)

The skill must detect whether a rebase is in progress and adjust the labels accordingly.

---

## Automation Script

A Python script at `hdb-merge-conflict-resolver/scripts/mergefix/` automates this skill:

```bash
# Dry run — show what would be resolved
python -m mergefix --dry-run

# Resolve all conflicts
python -m mergefix

# Resolve with a specific model
python -m mergefix --model claude-sonnet-4-20250514

# Specify a database path for logging
python -m mergefix --database /tmp/mergefix.db

# Verbose output
python -m mergefix --dry-run --verbose
```

The script follows the same modular pattern as `splitpr_05`:
- `cli.py` — Click CLI and top-level orchestration
- `git_ops.py` — All git commands via subprocess
- `ai.py` — Anthropic SDK integration for conflict analysis
- `db.py` — SQLite schema and helpers for logging resolutions
- `models.py` — Dataclasses shared across modules
- `resolver.py` — Core resolution engine that coordinates parsing, AI calls, and application
- `__main__.py` — Entry point

## Guidelines

- **Never auto-resolve low-confidence conflicts.** Present them to the user for manual review.
- **Always log every resolution.** The SQLite database is the audit trail.
- **Prefer diff3 format.** Recommend it to the user if not already enabled.
- **Handle rebase ours/theirs swap.** The skill must detect the operation type and label sides correctly.
- **Skip binary files and lock files.** These cannot be resolved by content merging.
- **Verify resolved files parse.** A resolution that produces syntax errors is worse than no resolution.
- **Respect --dry-run.** Never modify the working tree when dry-run is active.
- **Respect CLAUDE.md.** The project's instructions override everything in this skill.

## See Also

- `/hdb:split-pr` — decompose an oversize branch into multiple focused PRs
- `/hdb:python-dev` — develop Python code rapidly and correctly
