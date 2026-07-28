# Security, Privacy and Data Lifecycle

## Access boundary

- Every private object query includes the authenticated user ID.
- Platform health, model usage and audit views require `is_admin` on the server; hiding navigation is only a usability measure.
- Production startup rejects default JWT secrets, SQLite, automatic table creation, wildcard origins and hosts, missing administrators, and an unprotected metrics endpoint.
- Refresh tokens cannot call access-token endpoints. Account deletion requires password re-verification and the literal `DELETE` confirmation.

## Network and ingestion

- Web imports, RSS and Webhook delivery reject loopback, private, link-local and reserved destinations.
- Redirects are disabled for Webhooks and web imports. Every redirect target must be validated before support is added.
- Uploads are size-limited and checked by extension, signature and parser. Archive traversal and active content are rejected.
- Source integrations must use official APIs or feeds and comply with source terms, attribution, rate limits and deletion requirements.

## Secrets and logs

- Secrets belong in the deployment secret manager, never Git, images, client bundles, audit payloads or exception responses.
- JSON logging redacts authorization, token, secret, password, cookie and API-key patterns.
- Operational pages expose boolean error presence, diagnostic IDs and aggregate counts, not raw credentials or private content.

## Retention and deletion

- Default operational retention is 365 days and may be changed with `DATA_RETENTION_DAYS`, never below 30 days.
- `run_retention.py` removes expired BI history, model usage and audit records. Legal holds must be handled outside this job.
- Deleting a knowledge document removes stored versions and excludes all deleted chunks from retrieval.
- Account deletion removes private storage first and then deletes user-owned database rows through foreign-key cascades. A storage deletion failure aborts account deletion so it can be retried safely.
- Public-source takedown requests are handled by marking content deleted, removing it from search/AI evidence, and retaining only the minimum audit record allowed by policy.

## Required security regression

- Unauthenticated and non-admin access to administrative endpoints.
- Refresh-token and forged-token access attempts.
- SSRF through IPv4, IPv6, DNS resolution, redirects, RSS, web import and Webhook fields.
- MIME spoofing, archive traversal, oversized and malformed uploads.
- Secret patterns in API errors, task logs, sync logs and JSON application logs.
- Cross-user knowledge, report, conversation, alert and saved-search access.

