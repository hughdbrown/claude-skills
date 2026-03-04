---
name: hdb:alembic
description: Diagnose and fix Alembic migration issues — broken chains, multiple heads, failed downgrades, and CI gate failures
---

# hdb:alembic

Diagnose and fix Alembic migration problems using invariants and patterns proven in production projects.

## Usage

```
/hdb:alembic <problem description or task>
```

## Description

Alembic migrations are a directed acyclic graph (DAG) where each revision points to its parent via `down_revision`. Most migration problems come from violating the invariants of this graph. This skill encodes those invariants, the diagnostic commands to detect violations, and the fixes for every common failure mode.

## Instructions

When the user invokes `/hdb:alembic <problem description>`:

### Phase 1: Diagnose

1. **Gather state.** Run these commands to understand the current migration state:

   ```bash
   # Current heads (should be exactly 1 in most projects)
   cd backend && uv run alembic heads

   # Current database revision (what's applied)
   cd backend && uv run alembic current

   # Full revision history
   cd backend && uv run alembic history --verbose

   # Check for graph integrity issues
   cd backend && uv run alembic check
   ```

2. **Read the migration files.** Look at the `down_revision` fields in every file under `migrations/versions/`. Build a mental model of the chain.

3. **Identify the invariant violation.** Match the symptoms to the invariants listed below.

### Phase 2: Fix

4. **Apply the appropriate fix** from the catalog below. Every fix preserves existing data and maintains reversibility.

5. **Verify the fix:**
   ```bash
   # Graph integrity
   cd backend && uv run alembic heads          # must show exactly 1 head
   cd backend && uv run alembic history         # must show linear chain (or explicit merges)

   # Full round-trip (requires a test database)
   cd backend && uv run alembic upgrade head
   cd backend && uv run alembic downgrade base
   cd backend && uv run alembic upgrade head
   ```

---

## Alembic Invariants

These are the rules that must hold for a healthy migration graph. Every migration problem is a violation of one or more of these invariants.

### Invariant 1: Single Head

**Rule:** There must be exactly one leaf node (head) in the migration DAG at any given time on a release branch.

**Why:** `alembic upgrade head` applies all migrations up to the head. If there are multiple heads, Alembic doesn't know which path to take and refuses to run.

**Check:**
```bash
cd backend && uv run alembic heads
```
If this shows more than one revision, you have multiple heads.

**Common cause:** Two PRs merged independently, each adding a migration with the same `down_revision` (both pointing to the previous head).

```
A → B → C (head on main)
         ↓
PR #1:   C → D₁ (down_revision = C)
PR #2:   C → D₂ (down_revision = C)

After both merge: C → D₁ (head)
                  C → D₂ (head)  ← TWO HEADS
```

### Invariant 2: Linear Chain (or Explicit Merges)

**Rule:** Every revision has exactly one `down_revision` (a single parent), except:
- The initial migration, which has `down_revision = None`
- Merge migrations, which have `down_revision = ("rev1", "rev2")` — a tuple of two parents

**Why:** A linear chain guarantees deterministic ordering. Merges are the only way to join two branches.

### Invariant 3: Referential Integrity

**Rule:** Every `down_revision` value must reference an existing revision ID in another migration file.

**Why:** A broken reference means Alembic cannot walk the graph. `alembic upgrade head` will fail with `Can't locate revision identified by '<id>'`.

**Check:**
```bash
cd backend && uv run alembic history --verbose 2>&1 | grep -i error
```

### Invariant 4: No Orphans

**Rule:** Every revision must be reachable by walking from a head backward through `down_revision` links.

**Why:** Orphaned revisions are dead code — they exist on disk but never run. They confuse developers and can cause merge conflicts.

### Invariant 5: Full Reversibility

**Rule:** Every `upgrade()` function must have a corresponding `downgrade()` that fully reverses it. The cycle `upgrade head → downgrade base → upgrade head` must succeed.

**Why:** Reversibility enables rollback in production and validates that no migration has hidden state dependencies.

**Check:**
```bash
cd backend && uv run alembic upgrade head
cd backend && uv run alembic downgrade base
cd backend && uv run alembic upgrade head
```

### Invariant 6: Idempotent Operations

**Rule:** Migrations should check for existence before creating or dropping objects.

**Why:** Migrations may be re-run during development, testing, or disaster recovery. A migration that fails on re-run is fragile.

```python
# Good: defensive
def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("my_table"):
        op.create_table(...)

# Bad: crashes on re-run
def upgrade() -> None:
    op.create_table(...)  # raises if table already exists
```

### Invariant 7: One Migration Per PR

**Rule:** Each PR should add at most one migration file.

**Why:** Multiple migrations in one PR increase merge conflict risk, complicate review, and make rollback harder. If you need multiple schema changes, combine them into one migration.

---

## Fixing Multiple Heads

This is the most common Alembic problem. There are two approaches:

### Fix A: Re-chain (preferred when one migration should come after the other)

If the two heads are logically sequential (D₂ should apply after D₁):

```python
# In D₂'s migration file, change:
down_revision = "C"
# To:
down_revision = "D₁"
```

This creates: `C → D₁ → D₂` (single head).

**When to use:** The migrations don't conflict and can be ordered arbitrarily, or there's a natural ordering.

### Fix B: Merge migration (when both branches must be preserved)

Create a new merge migration:

```bash
cd backend && uv run alembic merge heads -m "merge D1 and D2"
```

This creates a new file with:
```python
down_revision = ("D₁", "D₂")

def upgrade() -> None:
    pass  # no-op, just merges the branches

def downgrade() -> None:
    pass
```

Result: `C → D₁ → M (head)`
         `C → D₂ ↗`

**When to use:** The two branches have conflicting operations that can't be reordered, or you need to preserve the exact commit history.

### Fix C: Squash (when the extra migration is unnecessary)

If one of the heads is empty, redundant, or can be folded into the other:

1. Delete the redundant migration file
2. Verify the remaining chain: `uv run alembic heads` (should show 1 head)

**When to use:** One migration was created by mistake or is a no-op.

---

## Fixing Broken References

**Symptom:** `Can't locate revision identified by 'abc123'`

**Cause:** A migration's `down_revision` points to a revision ID that doesn't exist (deleted, renamed, or typo).

**Fix:**
1. Find the migration file with the broken reference
2. Identify what the `down_revision` should actually be (look at `alembic history` or the other files)
3. Correct the `down_revision` value
4. Verify: `uv run alembic heads` and `uv run alembic history`

---

## Fixing Failed Downgrades

**Symptom:** `alembic downgrade` fails mid-way.

**Common causes:**
1. **Missing `downgrade()` body** — the function is `pass` or incomplete
2. **Data dependency** — the downgrade drops a column that a constraint references
3. **Type conversion not reversible** — e.g., Float → Integer loses precision

**Fix pattern:**
```python
def downgrade() -> None:
    # Drop constraints BEFORE dropping columns
    op.drop_constraint("fk_my_table_other_id", "my_table", type_="foreignkey")
    # Drop indexes BEFORE dropping tables
    op.drop_index("ix_my_table_column", table_name="my_table")
    # Now safe to drop
    op.drop_column("my_table", "column_name")
    # Or drop entire table
    op.drop_table("my_table")
```

**Order matters in downgrades:**
1. Drop foreign key constraints first
2. Drop indexes
3. Drop columns
4. Drop tables

This is the reverse of the upgrade order (create table → add columns → add indexes → add constraints).

---

## Fixing Data Migrations

Data migrations (INSERT, UPDATE, DELETE) require special care in downgrades.

**Pattern:**
```python
def upgrade() -> None:
    # Add column
    op.add_column("tasks", sa.Column("board_id", sa.Uuid()))
    # Backfill from related table
    op.execute("""
        UPDATE tasks SET board_id = agents.board_id
        FROM agents WHERE tasks.agent_id = agents.id
    """)

def downgrade() -> None:
    # No need to undo the data — just drop the column
    op.drop_column("tasks", "board_id")
```

**Rule:** Downgrade of a data migration drops the column/table. You don't need to "un-backfill" data.

---

## Creating a New Migration

```bash
cd backend && uv run alembic revision --autogenerate -m "add foo column to bars"
```

**After autogeneration, always:**
1. **Read the generated file.** Autogenerate guesses; it can miss renames (interprets as drop+add), miss data migrations entirely, and generate incorrect type mappings.
2. **Verify `down_revision`** points to the current single head.
3. **Add defensive checks** for idempotency where appropriate.
4. **Write a complete `downgrade()`** function.
5. **Test the full round-trip:**
   ```bash
   uv run alembic upgrade head
   uv run alembic downgrade -1    # undo just this migration
   uv run alembic upgrade head    # re-apply
   ```

---

## CI Gate: `backend-migration-check`

The CI pipeline validates migrations with this sequence:

```bash
# 1. Validate graph structure (no multiple heads, no orphans)
cd backend && uv run python scripts/check_migration_graph.py

# 2. Spin up ephemeral Postgres
docker run -d --rm -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=migration_ci \
    -p 55432:5432 postgres:16

# 3. Full round-trip test
AUTH_MODE=local \
LOCAL_AUTH_TOKEN=<long-token> \
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/migration_ci \
BASE_URL=http://localhost:8000 \
    uv run alembic upgrade head
    uv run alembic downgrade base
    uv run alembic upgrade head

# 4. Cleanup
docker rm -f <container>
```

**If CI fails:**
1. Read the error message — it tells you which step failed
2. If `check_migration_graph.py` fails → you have multiple heads or broken references
3. If `upgrade head` fails → a migration has a syntax error or incompatible operation
4. If `downgrade base` fails → a migration's `downgrade()` is incomplete
5. If the second `upgrade head` fails → a migration isn't idempotent
6. If it fails with `ValidationError` for missing settings → add the required env vars (AUTH_MODE, LOCAL_AUTH_TOKEN, DATABASE_URL, BASE_URL)

---

## Environment Variables for Migration Commands

The application's `Settings` class validates required fields at import time. When running Alembic commands (which import `app.core.config`), you must set:

```bash
AUTH_MODE=local
LOCAL_AUTH_TOKEN=<at-least-32-chars>
DATABASE_URL=postgresql+psycopg://user:pass@host:port/dbname
BASE_URL=http://localhost:8000
```

If you get a Pydantic `ValidationError` when running `alembic`, you're missing one of these.

---

## env.py: How Alembic Finds Models

The `migrations/env.py` file:
1. Imports `app.models` (which registers all SQLModel classes)
2. Uses `SQLModel.metadata` as the target metadata
3. Normalizes `postgresql://` to `postgresql+psycopg://` for the psycopg3 driver
4. Uses `NullPool` for migrations (no connection pooling needed)
5. Enables `compare_type=True` to detect column type changes

**If autogenerate misses your model:** Make sure it's imported in `app/models/__init__.py`.

---

## Common Pitfalls

### 1. Autogenerate creates drop+add instead of rename
Alembic cannot detect renames. It sees "column A disappeared, column B appeared" and generates `drop_column` + `add_column`. **Fix:** Replace with `op.alter_column(..., new_column_name=...)`.

### 2. Enum types on PostgreSQL
Adding or removing enum values requires special handling:
```python
# Adding a value (PostgreSQL)
op.execute("ALTER TYPE myenum ADD VALUE 'new_value'")

# Downgrade: PostgreSQL cannot remove enum values!
# You must recreate the type and migrate data.
```

### 3. SQLite vs PostgreSQL differences in tests
If tests use SQLite (`:memory:`) but production uses PostgreSQL, some operations behave differently:
- SQLite doesn't enforce foreign keys by default
- SQLite doesn't support `ALTER COLUMN`
- SQLite doesn't have enum types
- Index and constraint naming differs

### 4. Alembic `batch_alter_table` for SQLite
When testing downgrades on SQLite, you may need batch mode:
```python
with op.batch_alter_table("my_table") as batch_op:
    batch_op.drop_column("column_name")
```
PostgreSQL doesn't need this, but it's harmless.

### 5. The `alembic_version` table
Alembic tracks the current revision in an `alembic_version` table with a single row. If this gets corrupted:
```bash
# Check current stamp
uv run alembic current

# Force-stamp to a specific revision (does NOT run migrations)
uv run alembic stamp <revision_id>

# Force-stamp to head (marks all as applied without running)
uv run alembic stamp head
```

**Warning:** `alembic stamp` changes the recorded version without running any upgrade/downgrade logic. Use only when you know the schema already matches.

---

## Diagnostic Cheat Sheet

| Symptom | Command | Likely Cause |
|---------|---------|--------------|
| `Multiple heads` | `alembic heads` | Two migrations share the same `down_revision` |
| `Can't locate revision` | `alembic history -v` | Broken `down_revision` reference |
| `Target database is not up to date` | `alembic current` | Pending migrations not applied |
| `Table already exists` | Read the migration file | Missing idempotency check |
| `Column not found` during downgrade | Read the downgrade function | Wrong drop order (constraint before column) |
| `ValidationError` on any alembic command | Check env vars | Missing AUTH_MODE, DATABASE_URL, or BASE_URL |
| `No such revision` | `alembic history` | Migration file deleted but still referenced |
| Autogenerate produces empty migration | Check `app/models/__init__.py` | Model not imported into metadata |

## Guidelines

- **Always test the full round-trip** (up → down → up) before committing a migration.
- **One migration per PR.** Combine related schema changes into a single file.
- **Read autogenerated migrations.** They are a starting point, not the final product.
- **Write defensive migrations.** Check existence before creating. Future-you will thank present-you.
- **Downgrade order is reverse of upgrade order.** Constraints → indexes → columns → tables.
- **Never edit a migration that has been applied to production.** Create a new migration to fix issues.
- **Fix multiple heads immediately.** They compound — every new PR adds another head if the base isn't fixed.
- **Respect CLAUDE.md.** The project's instructions override everything in this skill.
