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


## Community workflow

Use the bug or feature form in `.github/ISSUE_TEMPLATE` and check the roadmap and capability matrix before opening a proposal. Pull requests should describe the user-visible outcome, include focused validation, and update documentation when a capability, credential, migration, or deployment boundary changes. UI changes should include a reproducible route or redacted screenshot. Do not commit `.env` files, cookies, tokens, local databases, logs, generated bundles, or private source material.

The default reviewer is listed in `.github/CODEOWNERS`. Security issues belong in `SECURITY.md`, not a public issue. Release notes follow `docs/12-release-notes-template.md` and the versioned examples under `docs/releases/`.
