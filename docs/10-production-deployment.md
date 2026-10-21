# Production Deployment and Operations

## Environments

- Staging uses `deploy/staging.compose.yml`: PostgreSQL 16 with pgvector, Redis 7, MinIO, a two-process API, web gateway and scheduler/knowledge/orchestration/media/sources/actions workers.
- Production uses `deploy/k8s/production.yaml` with managed PostgreSQL 16 (the `vector` extension must be available), Redis and S3-compatible storage supplied through `infopulse-secrets`.
- Staging and production must use different clusters or accounts, databases, buckets, Redis instances, mail senders, model keys and source tokens.

## Release flow

1. Merge only after the Release Gate succeeds.
2. Create immutable API and web images using a commit SHA tag.
3. Bootstrap a versioned ConfigMap, verify the Secret and bound RWX export PVC, and snapshot application resources. Run the isolated preflight Job and wait for success.
4. Apply only the migration Job and wait for completion before updating deployments.
5. Deploy the canary at zero public traffic. Check its exact image tag and probe readiness directly through its own service port-forward.
6. Set the selected canary weight, then promote API/web and every worker. Set canary traffic back to zero after rollout succeeds. Image digest pinning and a timed metrics observation window remain follow-up work.
7. On failure, restore the snapshotted API/web/worker deployments and managed services, ingresses, policies, HPA and PDB resources. Remove managed resources introduced by the failed release. Schema, Secret and persistent storage are retained; migrations must remain compatible with the old application.

The template sets web Ingress body size to 260m and explicitly permits web Pod requests to API TCP 8000. Render/ordering/rollback tests cover the manifests; real CNI, ingress limits and cluster rollback still require staging acceptance. See the [current audit acceptance](./audits/2026-10-21-remediation.md).

## Shared report exports

All API replicas and the knowledge cleanup worker require the same `REPORT_EXPORT_PATH`. Compose mounts `staging_exports` at `/shared/exports`. Before Kubernetes deployment, separately provision the `infopulse-exports` ReadWriteMany claim using a real cluster StorageClass; see `deploy/k8s/exports-pvc.example.yaml`. The workflow rejects missing, non-RWX or unbound claims. Back up the export volume with database metadata and retain it on rollback.

Existing ReportExport rows contain absolute paths. Preserve the old path as a shared mount, or stop writes, back up, copy and verify files, and update storage keys before switching paths. A new empty volume alone does not migrate existing exports. Monitor storage cleanup outbox attempts and errors; do not drop failed records to hide incomplete deletion.

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
