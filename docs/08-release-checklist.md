# Release Checklist

## Scope: local developer preview versus production

InfoPulse currently targets a local `v0.x` developer preview. Publishing source code is not production certification. The production gates below remain requirements, not a claim that they have passed. Real provider credentials may remain empty; unavailable integrations must report their limits and must not simulate success.

For each preview PR, record its exact scope, tests, environment, artifact paths and remaining limitations in the [roadmap evidence](./audits/2026-10-13-roadmap-progress.md). Only mark that scope complete after actual verification. Merge only the checked head after all Release Gate and CodeQL jobs pass; do not reuse results from an older commit.

Current automated coverage includes Linux backend tests, Windows Python 3.10/3.11 full dependencies/tests, the 354-path API schema snapshot, frontend tests/types/build/bundle budgets, SDK build, dependency audits, Linux dual-version PostgreSQL/browser acceptance and minimal/full container acceptance. The full image additionally runs real Chromium and synthetic ffmpeg fixtures. PostgreSQL populated migration/recovery coverage is explicitly limited to the documented 14 core tables and knowledge worker.

Unchecked roadmap items are not waived by these jobs: all-button negative UI cases, other worker recovery, full populated migration coverage, external provider quality, backup restore, load/SLO targets and governance need their own evidence. The production commands below may change data or call configured services; do not run them against an unknown or personal environment just to fill a checklist.

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
