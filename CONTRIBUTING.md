# Contributing

## Development Setup

Follow the local setup in `README.md`. Keep secrets in ignored `.env` files and
use SQLite when PostgreSQL is not required for the change.

## Before Opening a Pull Request

Run:

```powershell
cd backend
python -m compileall -q app tests scripts
python -m unittest discover -s tests -v
python scripts/api_contract_check.py

cd ..\frontend
npm ci
npm run build
```

Add focused tests for behavior changes. Database schema changes require an
Alembic migration with working upgrade and downgrade paths. Do not commit
generated databases, logs, build output, credentials, platform cookies, or
private crawler plugins.

## Scope and Safety

Collectors must use public or explicitly authorized data sources. Changes must
not bypass authentication, CAPTCHAs, access controls, platform restrictions, or
data-retention requirements. AI-generated claims must retain their source and
uncertainty metadata.
