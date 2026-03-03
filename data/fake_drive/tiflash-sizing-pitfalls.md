# Columnar Replica Sizing Pitfalls

Columnar replicas can accelerate analytical workloads, but overprovisioning or underprovisioning can increase cost or lag.

## Common Pitfalls

- Enabling replicas before validating query patterns.
- Ignoring replication lag during ingest spikes.
- Treating all analytical tables equally without criticality ranking.

## Recommendations

- Start with critical datasets and roll out in phases.
- Define acceptable freshness windows for user-facing analytics.
- Measure p95 and p99 query latency and tune replica strategy iteratively.
