# Release Checklist

## Automated gate

- Backend compile and all unit/security tests pass with external AI keys disabled.
- Frontend type check and production build pass.
- Alembic upgrades to head, downgrades one revision and upgrades again.
- `production_check.py` reports one migration head and no unsafe configuration.
- Target load profile has zero failed requests and meets the agreed p95 threshold.

## Operational gate

- P0/P1 defects: zero.
- Dashboard, search, event, Agent, report, alert, BI and knowledge workflows use real data or explicit empty states.
- Metrics collection, log ingestion, alerts and on-call ownership are active.
- Latest backup restore drill is successful and documented.
- Source failure, worker restart and Webhook dead-letter drills are successful.
- Account deletion and knowledge deletion have been verified in the release candidate environment.
- Source terms, privacy notice, retention period and deletion contact are approved.
- Previous image, rollback procedure and database compatibility have been confirmed.

## Production commands

```powershell
cd backend
python scripts/production_check.py
alembic upgrade head
python scripts/run_retention.py
python scripts/load_test.py --base-url https://api.example.com --requests 1000 --concurrency 25 --max-p95-ms 500
```

Release approval must include links to CI, load results, restore evidence and the completed incident drill record.
