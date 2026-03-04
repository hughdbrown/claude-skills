#  Invariants:
  1. Single head — one leaf node in the DAG
  2. Linear chain (or explicit merges) — every revision has exactly one parent
  3. Referential integrity — every down_revision must exist
  4. No orphans — every revision reachable from heads
  5. Full reversibility — up → down → up must succeed
  6. Idempotent operations — check existence before create/drop
  7. One migration per PR

#  Fixes for common problems:
  - Multiple heads — three approaches: re-chain, merge migration, or squash
  - Broken references — find and correct the down_revision
  - Failed downgrades — correct drop order (constraints → indexes → columns → tables)
  - Data migrations — backfill in upgrade, just drop column in downgrade
  - CI gate failures — env var checklist, step-by-step diagnosis
  - Autogenerate pitfalls — renames, enums, SQLite vs PostgreSQL

#  Project-specific knowledge baked in:
  - The env var requirements (AUTH_MODE, LOCAL_AUTH_TOKEN, DATABASE_URL, BASE_URL)
  - The check_migration_graph.py validator
  - The full CI round-trip sequence from the Makefile
  - The one_migration_per_pr.sh enforcement
  - The env.py driver normalization (postgresql:// → postgresql+psycopg://)
