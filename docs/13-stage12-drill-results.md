# Stage 12 staging drill results

Drill date: 2026-07-29 (Asia/Shanghai)

## Scope

The drill used the isolated Compose project `infopulse-stage12-drill`. It exercised PostgreSQL 16 with pgvector, Redis 7 and MinIO using disposable local volumes. No production data or credentials were used.

## Results

| Check | Result |
| --- | --- |
| Alembic migration | Upgraded an empty PostgreSQL database through revision `20260729_0014` |
| PostgreSQL backup | Custom-format `pg_dump` completed in 0.187 seconds |
| PostgreSQL restore | Restored into a separate `infopulse_restore` database in 1.070 seconds |
| Restore integrity | Source and restore both reported revision `20260729_0014`, 4 seeded data sources and 53 public tables |
| Redis | `redis-cli ping` returned `PONG` |
| S3-compatible storage | MinIO was healthy and the `infopulse-knowledge` bucket was listed successfully |

## Finding and remediation

The first migration attempt failed because the generic `postgres:16-alpine` image did not provide the `vector` extension required by migration `0010`. Staging now uses `pgvector/pgvector:pg16`, and the production deployment guide explicitly requires managed PostgreSQL with pgvector available.

## Production boundary

This is a local staging drill, not evidence of a production failover. A production exercise still requires approved cloud accounts, a maintenance window, managed-service snapshots, DNS and traffic controls, production monitoring, and named incident owners. Record the provider snapshot identifier, recovery point, recovery time and validation queries in the incident system when that exercise is authorized.
