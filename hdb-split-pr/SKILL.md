---
name: hdb:split-pr
description: Decompose an oversize branch into multiple focused PRs with dependency ordering and detailed task lists
---

# hdb:split-pr

Decompose an oversize branch into multiple focused, non-overlapping PRs with correct dependency ordering and detailed recovery tasks.

## Usage

```
/hdb:split-pr [--base <branch>] [--dry-run]
```

## IMPORTANT

This skill produces two artifacts: (1) a **partition plan** mapping every change to exactly one PR, and (2) a **detailed task list** per PR that captures specific changes from the original branch. The goal is maximum recovery of past work with no overlap between PRs.

## Description

When a branch accumulates too many changes for a single reviewable PR (rough threshold: >15 files changed, >500 net insertions, or >3 distinct themes), this skill decomposes it into multiple smaller PRs. Each PR is coherent (single theme), self-contained (passes tests independently), and non-overlapping (no file change appears in two PRs). The PRs are ordered so dependencies are satisfied: PR A merges before PR B if B depends on changes from A.

After partitioning, the skill generates detailed tasks for each PR — each task references specific files, original commits, and code from the source branch so the implementer can recover the exact changes efficiently.

## Instructions

When the user invokes `/hdb:split-pr [--base <branch>] [--dry-run]`:

### Phase 1: Inventory

Catalog everything on the branch before making any decisions.

1. **Determine the base branch.** If `--base` is provided, use it. Otherwise detect:

   ```bash
   git merge-base master HEAD
   ```

   If neither `master` nor `main` exists, ask the user to specify the base.

2. **List all commits** on the branch since divergence:

   ```bash
   git log --oneline --reverse $(git merge-base <base> HEAD)..HEAD
   ```

   Record the count. If there are fewer than 5 commits and fewer than 10 files changed, inform the user the branch is small enough for a single PR and stop unless they insist.

3. **List all changed files** with diff stats:

   ```bash
   git diff --stat <base>..HEAD
   git diff --name-only <base>..HEAD | sort
   ```

4. **Read every commit message** and categorize each commit by its logical theme. Use the commit message prefix (e.g., `security:`, `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`) as the primary signal. When the prefix is ambiguous, read the commit's diff:

   ```bash
   git show --stat <sha>
   ```

5. **Build the theme inventory table.** Present it to the user for review:

   | Theme | Commits | Files | Net Lines | Description |
   |-------|---------|-------|-----------|-------------|
   | rate-limiting | 8 | 5 | +320 | In-memory and Redis rate limiter |
   | webhook-security | 6 | 4 | +180 | HMAC verification, payload limits |
   | ... | ... | ... | ... | ... |
   | **TOTAL** | **62** | **43** | **+1913** | |

6. **Identify cross-cutting files** — files touched by commits from multiple themes:

   ```bash
   # For each file, list which themes' commits touch it
   git log --format="%h %s" <base>..HEAD -- <file>
   ```

   Present cross-cutting files in a separate table:

   | File | Themes | Decision Needed |
   |------|--------|-----------------|
   | `backend/app/core/config.py` | rate-limiting, webhook-security | Which PR owns the config changes? |
   | `backend/app/main.py` | rate-limiting, auth-refactor | Middleware registration spans two features |

7. **Wait for user confirmation** of the theme groupings before proceeding. The user may want to merge themes, split themes, or rename them.

### Phase 2: Dependency Analysis

Determine the merge order.

8. **For each theme group, identify dependencies on other groups.** A theme depends on another if:
   - It imports or calls functions introduced by the other theme
   - It modifies files whose baseline state requires the other theme's changes
   - Its tests rely on fixtures or utilities introduced by the other theme
   - It extends a database migration introduced by the other theme

   Check dependencies by reading the diffs:
   ```bash
   git diff <base>..HEAD -- <file>
   ```

9. **Build the dependency DAG.** Present it as a table and an ASCII diagram:

   | PR | Theme | Depends On | Merge Order |
   |----|-------|------------|-------------|
   | 1 | auth-refactor | (none) | First |
   | 2 | rate-limiting | auth-refactor | Second |
   | 3 | webhook-security | auth-refactor | Second (parallel with 2) |
   | 4 | docs | rate-limiting, webhook-security | Third |

   ```
   1:auth-refactor
   ├── 2:rate-limiting
   ├── 3:webhook-security
   └── 4:docs (after 2+3)
   ```

10. **Detect cycles.** If the dependency graph has a cycle, the themes cannot be cleanly separated. Options:
    - Merge the cyclic themes into a single PR
    - Extract shared infrastructure into a new "foundation" PR that breaks the cycle

    Present the cycle to the user and recommend a resolution.

11. **Wait for user confirmation** of the dependency ordering before proceeding.

### Phase 3: Partition

Assign every file change to exactly one PR.

12. **Assign unambiguous files first.** Files touched by only one theme go into that theme's PR. This handles the majority of files.

13. **Resolve cross-cutting files.** For each cross-cutting file, choose one strategy:

    | Strategy | When to Use | How |
    |----------|-------------|-----|
    | **Assign to earliest PR** | The file has a clear "foundation" change that later PRs build on | Put all changes in the earliest PR in the dependency chain |
    | **Split by hunk** | The file has distinct, non-overlapping hunks for each theme | Extract per-theme patches and partition hunks |
    | **Assign to infrastructure PR** | The file is shared config or wiring (e.g., `main.py`, `config.py`) | Create a dedicated "infrastructure" PR or assign to the first PR |
    | **Sequential layering** | One theme adds a function, another modifies it | Put the addition in the earlier PR; the modification in the later PR (which rebases on top) |

14. **Handle special file categories:**

    | Category | Strategy |
    |----------|----------|
    | **Formatting/linting commits** | Assign each formatted file to whichever PR already owns that file. If a formatting commit touches files across multiple PRs, split it. |
    | **Test files** | Move test files with the feature they test. If a test file covers multiple features, assign it to the latest PR in the dependency chain or create a dedicated test PR. |
    | **Documentation** | Small doc changes travel with their feature. Large doc additions (new files, multi-file updates) go in a dedicated docs PR at the end of the chain. |
    | **Migration files** | Migrations travel with the schema change they implement. If two migrations exist, they go in separate PRs only if independent. Chain `down_revision` values accordingly. |
    | **Docker/CI/Makefile** | Infrastructure config goes in the earliest PR that needs it, or in a dedicated infrastructure PR. |

15. **Build the partition table.** Present it to the user:

    | PR | Branch Name | Theme | Files | Cherry-Pick Candidates |
    |----|-------------|-------|-------|------------------------|
    | 1 | `security/auth-refactor` | Auth renaming | `deps.py`, `admin_access.py`, ... | `00102f8`, `f102b50` |
    | 2 | `security/rate-limiting` | Rate limiting | `rate_limit.py`, `rate_limit_backend.py`, ... | `603c653`, `0d5f4bf`, ... |
    | ... | ... | ... | ... | ... |

16. **Verify completeness.** The union of all file lists must equal the original changed file list. No file may appear in two PRs:

    ```
    Original files: 43
    Assigned files: 43 (sum across all PRs)
    Duplicates: 0
    Unassigned: 0
    ```

    If there are unassigned files or duplicates, resolve them before proceeding.

17. **Wait for user confirmation** of the partition before generating tasks.

### Phase 4: Task Generation

For each PR, generate a detailed task list that captures the specific changes from the original branch.

18. **For each PR, generate ordered tasks.** Each task must have:

    - **Subject** — imperative action (e.g., "Add Redis rate limiter module")
    - **Description** — specific file paths, what to change, and references to original commits/diffs:
      ```
      Create `backend/app/core/rate_limit.py` with:
      - RateLimiter ABC with async `is_allowed(key: str) -> bool`
      - InMemoryRateLimiter using sliding-window deque
      - RedisRateLimiter using sorted-set pipeline
      - Shared client factory `_get_async_redis(url)`
      - `create_rate_limiter()` factory function

      Reference: commits 603c653, 32f5453, 294f518 on chore-security-review
      Recovery: `git show chore-security-review:backend/app/core/rate_limit.py`
      ```
    - **Acceptance criteria** — how to verify the task is done:
      ```
      - File exists and passes `mypy --strict`
      - `uv run pytest tests/test_rate_limit.py` passes (15 tests)
      ```

19. **Task ordering within each PR:**

    | Order | Task Type | Example |
    |-------|-----------|---------|
    | 1 | Infrastructure / new modules | Create `rate_limit_backend.py` enum |
    | 2 | Core implementation | Create `rate_limit.py` with ABC + both backends |
    | 3 | Configuration | Add settings to `config.py` |
    | 4 | Integration / wiring | Wire rate limiter into `agent_auth.py`, `board_webhooks.py` |
    | 5 | Tests | Create `test_rate_limit.py` with 15 tests |
    | 6 | Documentation | Update `security.md`, `api.md` |
    | 7 | Linting / formatting | Run `ruff`, `black`, `isort` and fix |
    | 8 | Commit and verify | Run full test suite, commit |

20. **Include recovery commands** in each task so the implementer can pull exact code from the source branch:

    ```bash
    # View the final state of a file on the source branch
    git show <source-branch>:<file-path>

    # View a specific commit's changes to a file
    git show <sha> -- <file-path>

    # Extract a file from the source branch into the working tree
    git checkout <source-branch> -- <file-path>

    # Generate a patch for specific files
    git diff <base>..<source-branch> -- <file-path> > /tmp/partial.patch
    ```

21. **Present the complete task list** to the user, organized by PR:

    ```
    ## PR 1: security/auth-refactor (Auth Renaming)
    Depends on: (none) | Base: master

    1. Rename `require_admin_auth` → `require_user_auth` in deps.py
       Recovery: git show chore-security-review:backend/app/api/deps.py
       Acceptance: All 10 API modules import the new name; tests pass

    2. Update all API modules to use renamed dependency
       Files: activity.py, agents.py, approvals.py, ...
       Recovery: git diff master..chore-security-review -- backend/app/api/activity.py
       Acceptance: `rg require_admin_auth backend/` returns 0 matches

    3. Run tests and commit
       Acceptance: `uv run pytest` passes; commit message follows conventions

    ## PR 2: security/rate-limiting (Rate Limiting)
    Depends on: PR 1 | Base: security/auth-refactor

    1. Create rate_limit_backend.py enum
       ...
    ```

### Phase 5: Extract (on user request)

Create the sub-PR branches. Work in dependency order (roots first, leaves last).

22. **Decide extraction method per PR:**

    | Method | When to Use | Pros | Cons |
    |--------|-------------|------|------|
    | **Cherry-pick** | Commits are clean and atomic; each commit belongs entirely to one PR | Preserves history | Fails when commits span multiple themes |
    | **File-level checkout** | Commits are mixed or squashed | Clean result regardless of commit structure | Loses original commit granularity |

    In practice, most splits use file-level checkout because real branches rarely have perfectly atomic commits.

23. **For each PR (in dependency order):**

    a. **Create a new branch** from the appropriate base:
    ```bash
    # For the first PR (no dependencies):
    git checkout -b <branch-name> <base>

    # For PRs that depend on a prior PR:
    git checkout -b <branch-name> <prior-pr-branch>
    ```

    b. **Apply the changes** using the chosen method:

    **Cherry-pick method:**
    ```bash
    git cherry-pick <sha1> <sha2> <sha3>
    ```

    **File-level checkout method:**
    ```bash
    git checkout <source-branch> -- <file1> <file2> <file3>
    git commit -m "<theme>: apply <description>"
    ```

    **Hunk-level extraction** (for cross-cutting files):
    ```bash
    git diff <base>..<source-branch> -- <file> > /tmp/partial.patch
    # Edit the patch to keep only relevant hunks
    git apply /tmp/partial.patch
    ```

    c. **Run tests** to verify the branch works standalone:
    ```bash
    cd backend && uv run pytest tests/ -x -q    # Python
    go test ./...                                 # Go
    cargo test                                    # Rust
    ```

    d. **Run linters/formatters** and fix any issues.

    e. **Verify the diff** is limited to this PR's assigned files:
    ```bash
    git diff --name-only <base-of-this-pr>..HEAD
    ```

24. **If `--dry-run` was specified**, stop after generating the partition table and task list. Do not create branches.

### Phase 6: Verify

Confirm completeness and correctness after all branches are created.

25. **Verify coverage.** For each file in the original diff, confirm it appears in exactly one sub-PR:

    ```bash
    for branch in <branch1> <branch2> ...; do
        echo "=== $branch ==="
        git diff --name-only <base>..$branch
    done
    ```

26. **Verify each branch passes tests independently.**

27. **Generate the final summary:**

    ```
    ## Split Summary

    Original branch: chore-security-review (62 commits, 43 files, +1913/-85)
    Sub-PRs created: 5

    | # | Branch | Theme | Files | Lines | Depends On | Tests | Tasks |
    |---|--------|-------|-------|-------|------------|-------|-------|
    | 1 | security/auth-refactor | Auth renaming | 12 | +120 | -- | PASS | 3 |
    | 2 | security/rate-limiting | Rate limiting | 8 | +450 | #1 | PASS | 8 |
    | 3 | security/webhook-hardening | Webhook security | 8 | +280 | #1 | PASS | 7 |
    | 4 | security/docker-hardening | Docker non-root | 3 | +30 | -- | PASS | 2 |
    | 5 | security/docs-and-tests | Docs + tests | 12 | +550 | #2, #3 | PASS | 5 |

    Merge order: 1 and 4 (parallel) → 2 and 3 (parallel) → 5
    Coverage: 43/43 files assigned. 0 duplicates. 0 unassigned.
    Total tasks: 25
    ```

### Phase 7: PR Creation (optional, on user request)

28. **Create PRs in dependency order:**

    ```bash
    git checkout <branch>
    git push -u origin <branch>
    gh pr create --base <target-base> --title "<theme>: <concise description>" --body "$(cat <<'EOF'
    ## Summary
    <1-3 bullet points>

    ## Context
    PR N of M from the `<original-branch>` split.
    **Merge order:** <where this fits>
    **Depends on:** <dependency PR links, or "None">

    ## Test plan
    - [ ] All existing tests pass
    - [ ] <specific items>

    Generated with [Claude Code](https://claude.com/claude-code)
    EOF
    )"
    ```

29. **Link dependency PRs** in each PR description so reviewers understand the merge order.

---

## Decision Guide: Cross-Cutting Files

| File Type | Resolution |
|-----------|--------------------|
| `config.py` / `settings.py` | Put in the earliest PR that needs the config. Later PRs add their settings on top via rebase. |
| `main.py` / app wiring | Put in a dedicated infrastructure PR, or in the earliest PR. |
| `Makefile` / `docker-compose.yml` | Put in the PR whose feature the change supports. |
| Shared test fixtures | Put in the earliest PR. Later PRs import from the fixture. |
| `__init__.py` / re-exports | Put in the PR that adds the module being re-exported. |
| Migration files | Always travel with the schema change they implement. |

## Common Pitfalls

### 1. Forgetting to rebase after merge

Later PRs were branched from earlier PR branches. After PR 1 merges into `master`, PR 2 must rebase:

```bash
git checkout security/rate-limiting
git rebase master
git push --force-with-lease
```

Failure to rebase causes the later PR to include the earlier PR's diff, confusing reviewers.

### 2. Tests that import across PR boundaries

If PR 2's tests import a helper added by PR 1, the tests fail when PR 2 is checked out before PR 1 merges. Solutions:
- Branch PR 2 from PR 1's branch (not from `master`)
- Duplicate the helper in PR 2 (acceptable for small helpers)
- Move the helper to a shared utility in PR 1

### 3. Migration ordering across PRs

If PR 2 and PR 3 both add Alembic migrations, they both have the same `down_revision`. When both merge, this creates multiple heads. Solutions:
- Put all migrations in one PR
- Use `alembic merge heads` after the second PR merges
- Chain the migrations: PR 3's migration depends on PR 2's

### 4. Formatting commits that touch everything

A single `ruff format .` commit touches every file. Do not put this in one PR. Instead:
- Re-run the formatter independently on each sub-PR branch
- Let each PR's files be formatted within that PR

### 5. Losing changes in the split

Always verify coverage (Phase 6, step 25). The most common cause: a file touched by two themes is assigned to only one PR, and the other theme's hunks are dropped.

### 6. Over-splitting

Not every theme needs its own PR. If two themes are small (< 3 files, < 50 lines each) and naturally related, merge them. The goal is reviewable PRs, not maximally granular PRs.

## Size Guidelines

| Original Size | Recommended Split |
|---------------|-------------------|
| 5-15 files, < 500 lines | Single PR (no split needed) |
| 15-30 files, 500-1000 lines | 2-3 PRs |
| 30-50 files, 1000-2000 lines | 3-5 PRs |
| 50+ files, 2000+ lines | 5-8 PRs (consider deferring some changes) |

## Guidelines

- **Get confirmation at each gate.** Present the theme inventory, dependency DAG, and partition table to the user before proceeding. Backtracking after branch creation is expensive.
- **Dependency order is non-negotiable.** Every PR must pass tests independently when applied on top of its declared dependencies.
- **Prefer file-level checkout over cherry-pick.** Real branches rarely have perfectly atomic commits.
- **Cross-cutting files go to the earliest PR.** When in doubt, put shared files in the first PR in the dependency chain.
- **Every task references recovery commands.** The implementer should be able to pull exact code from the source branch for each task.
- **Run tests on every sub-PR branch.** Do not assume a clean partition means clean tests.
- **Do not over-split.** Fewer, larger PRs are better than many tiny PRs that create a long merge queue. Target 3-6 PRs.
- **Document the merge order in every PR.** Reviewers need to know "this is PR 2 of 5, depends on PR 1."
- **Delete the original branch after all sub-PRs merge.** It is dead weight after the split.
- **Respect CLAUDE.md.** The project's instructions override everything in this skill.

## See Also

- `/hdb:design` — design a feature with a PRD and task list (use before implementing, to prevent oversize branches)
- `/roborev:pull-request-reviewer` — pre-review a PR before submitting
- `/hdb:alembic` — diagnose and fix migration issues that arise during splits
