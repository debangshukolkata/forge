---
name: sql-migration-raw
description: Write a raw SQL migration script in the repo's SQL folder (naming/numbering, idempotent DDL, rollback section, scratch-schema trial, DB requests).
---
# Raw SQL migrations

1. List the repo's SQL folder; follow its naming and numbering exactly (e.g. `V004__add_claim_notes.sql`).
2. Idempotent where existing scripts are: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`,
   `CREATE INDEX IF NOT EXISTS`. Match their header comment style.
3. End with a commented rollback section (`-- Rollback:` + the exact reverse statements).
4. Never touch other schemas explicitly; no DROP of anything that existed before.
5. Try it in the scratch schema with `scratch_exec` (create the tables it depends on there first, from the
   earlier scripts). If there is no scratch schema, write a `db_request` with the SQL and a verification
   query, and `mark_server_run` any DB-backed tests — never claim it was checked.
6. The script lands in output/ and in DB_CHANGES.sql in run order automatically.
