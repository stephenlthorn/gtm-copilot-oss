# Distributed SQL Online DDL Guidelines

The platform supports online schema changes through asynchronous DDL jobs.
For large tables, monitor change progress and schedule heavy updates outside peak ETL windows.

## Operational Guidance

- Estimate backfill time using representative row counts and index complexity.
- Track cluster headroom during online DDL to avoid query regressions.
- For business-critical changes, run a staging rehearsal with realistic data volume.

## GTM Positioning

When competitors claim faster schema operations, position on operational safety,
controlled rollout, and observability under sustained workload.
