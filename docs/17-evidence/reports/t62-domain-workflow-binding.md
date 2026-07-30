# T-62 domain workflow binding evidence

Verified on 2026-07-18 against the Docker demo API and PostgreSQL database after applying migration
`20260910_075_t62_binding`.

The evidence fixture creates a configurable `Governed material records` Table and a Record for the
seeded `DP780 synthetic demo steel`. The Record revision is bound to the exact governed Material
identity and revision. The Workflow Explorer shows both revision pins and offers `Open governed
object`, which resolves to the existing Material workbench rather than a second copy of the data.

![Catalog Record bound to the exact governed Material revision](../images/historical-task-screenshots/t62-domain-workflow-binding.png)

Verification included:

- clean Alembic upgrade and T-62 downgrade/upgrade on PostgreSQL 16;
- API create/read/graph projection tests;
- PostgreSQL trigger rejection of a missing target and mutation of an existing binding;
- web component navigation test for a bound graph node;
- Docker API, web, worker, and migration services rebuilt from this branch.

This fixture is product evidence for T-62 only. T-65 owns the deterministic, clean-volume
three-family demo genealogy that will create all Catalog Records and bindings during normal demo
seeding.
