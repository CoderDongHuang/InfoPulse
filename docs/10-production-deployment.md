# Production Deployment and Operations

## Environments

- Staging is reproducible with `deploy/staging.compose.yml`: PostgreSQL 16, Redis 7, MinIO, a two-process API, scheduler worker, knowledge worker and web gateway.
- Production uses `deploy/k8s/production.yaml` with managed PostgreSQL, Redis and S3-compatible storage supplied through `infopulse-secrets`.
- Staging and production must use different clusters or accounts, databases, buckets, Redis instances, mail senders, model keys and source tokens.

## Release flow

1. Merge only after the Release Gate succeeds.
2. Create immutable API and web images using a commit SHA tag.
3. Run `deployment_preflight.py` without printing credential values.
4. Apply the migration Job and wait for completion before traffic changes.
5. Deploy one canary replica and route 5-10% traffic through the canary Ingress.
6. Verify readiness and the 5xx/latency alerts. Promote the exact image digest to stable.
7. The deployment workflow sets canary traffic to zero and rolls back both deployments when verification fails.

Production deployment is manual through the protected GitHub `production` environment. Require two reviewers and restrict the environment to the default branch. Staging may use a separate kubeconfig and the same namespace because it is a separate cluster.

## Domain, TLS, CDN and WAF

- Point `app` and `api` DNS records to the ingress load balancer only after staging verification.
- cert-manager issues and renews TLS certificates. Reject HTTP at the load balancer and use TLS 1.2 or newer.
- Put the web host behind a CDN; cache hashed `/assets/` only. Never cache authenticated `/api/` responses.
- Configure the WAF for managed OWASP rules, bot protection, request body limits and 30 requests/second API rate limiting with a bounded burst.
- Preserve the original client IP only through trusted proxy headers. The edge must overwrite, not append user-supplied forwarding headers.

## Credentials

The production preflight requires PostgreSQL, Redis, S3, SMTP, model and GitHub source credentials. Hacker News, DEV.to and arXiv use public official endpoints and have no secret. Webhook signing secrets remain per-user encrypted application data; delivery still validates every destination against SSRF rules.

Never place real values in `.env.production.example`, Kubernetes YAML, image layers, workflow logs or release records. Rotate a credential immediately if preflight or a provider test exposes it.

## Backup and failover drill

1. Create an explicitly empty restore database and run `backup_restore_drill.py`.
2. Compare migration version and representative counts for users, content, events, reports and knowledge metadata.
3. Trigger failover only in staging or through the managed provider's approved production drill.
4. Run `failover_verify.py --ready-url https://api.example.com/api/v1/health/ready --max-rto-seconds 300`.
5. Verify task idempotency, no duplicate notifications, S3 access and a test knowledge retrieval.
6. Attach RTO, RPO, provider event ID and count comparison to the release record.

The repository provides the executable drill. A real production drill cannot be claimed until cloud resources and an approved maintenance window exist.

