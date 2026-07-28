# Production Runbook

## Service objectives

- Availability target: 99.9% monthly for authenticated API requests.
- Read API p95 target: 500 ms under the agreed production load profile.
- Write API p95 target: 1,000 ms, excluding asynchronous export and AI generation.
- No P0 or P1 defect may remain open at release time.

## Monitoring

- `GET /api/v1/health/live`: process liveness; restart the container when it fails.
- `GET /api/v1/health/ready`: database and Redis status; remove the instance from traffic on HTTP 503.
- `GET /api/v1/metrics`: Prometheus text, protected by `X-Metrics-Token`.
- Alert on 5xx rate above 2% for five minutes, p95 above the objective for ten minutes, a source failing three consecutive syncs, dead-letter deliveries, or no successful scheduled task in two expected intervals.
- Logs are JSON and correlated with `X-Request-ID`. Request bodies, authorization headers, cookies and private document text must never be logged.

## Incident response

1. Assign an incident owner and record the first diagnostic ID.
2. Check readiness, database saturation, worker backlog, source health and recent deployment changes.
3. Disable the affected source or scheduler before disabling the whole API.
4. Roll back the application only when the current database schema remains backward compatible. Never downgrade a production schema without a tested backup.
5. Record impact, timeline, mitigation and follow-up tests.

## Failure drills

- External source: block one provider, run its sync, verify a failed `SyncRun`, source health degradation and continued operation of other sources.
- Worker: stop the scheduler for two polling intervals, restart it, and verify idempotency keys prevent duplicate runs.
- Webhook: return 500 and timeouts, verify bounded retries followed by dead-letter state; private and redirecting destinations must remain rejected.
- Redis: stop Redis, verify readiness reports degraded while database-backed reads remain available.
- Database: stop a replica or drill database only, verify readiness returns 503 and no write is acknowledged.

## Backup and restore

Run `python backend/scripts/backup_restore_drill.py` against an explicitly created empty drill database. The script refuses identical source and restore URLs and requires `--confirm RESTORE_INTO_EMPTY_DRILL_DATABASE`. Record archive time, restore time, migration check and a sample count comparison. Perform the drill before each major release and at least quarterly.

## Rollback

- Keep the previous immutable image and configuration revision.
- Stop workers before rollback to prevent mixed-version processing.
- Restore application first when migrations are backward compatible.
- For data corruption, isolate writes, preserve evidence, and restore into a new database before switching traffic.

