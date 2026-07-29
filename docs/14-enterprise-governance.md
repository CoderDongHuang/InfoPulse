# Enterprise multi-tenancy and governance

## Tenant boundary

Every account receives a personal organization and workspace at registration. Enterprise requests resolve an active membership from `X-Organization-ID` and optionally require a matching workspace membership from `X-Workspace-ID`.

PostgreSQL migration `0015` enables row-level security on organization-owned tables. API transactions set `app.user_id` and `app.organization_id` with transaction-local `set_config` calls. Production must use a non-owner application database role so table-owner RLS bypass cannot weaken this boundary. Migration and maintenance roles must not serve API traffic.

Legacy private objects remain isolated by `user_id`. New model usage has explicit organization and workspace attribution; cost reports do not infer cost from membership because one user can belong to several organizations.

## Roles, approvals and legal holds

Built-in roles are `owner`, `admin` and `member`. Custom roles accept only permission literals declared in `schemas/enterprise.py`. High-risk operations use approval requests, and requesters cannot approve their own requests. Cost-limit increases above two times are rejected until an approved budget workflow is applied.

Legal holds accept only global, user or workspace scope. A matching hold blocks account and knowledge deletion with HTTP 409. Audit exports are organization-scoped, capped at 5,000 records and returned with `Cache-Control: no-store`.

## OIDC and SAML

InfoPulse uses a trusted identity broker for OIDC and SAML. Deploy oauth2-proxy, Keycloak, Entra Application Proxy or an equivalent reviewed broker in front of `POST /api/v1/auth/sso/exchange`. The broker validates discovery, PKCE, nonce, assertion signature, audience, issuer and clock claims, then forwards:

```text
X-SSO-Proxy-Secret: injected shared secret
X-SSO-Organization: organization slug
X-SSO-Email: verified email claim
X-SSO-Subject: stable provider subject
```

`SSO_PROXY_SECRET` must contain at least 32 random characters and come from the production secret manager. The exchange rejects disabled providers and disallowed email domains. Provider records contain only public metadata; client secrets and private keys are never stored in the application database. Ingress must restrict the exchange path to the identity broker network.

## SCIM 2.0

The SCIM base path is `/api/v1/scim/v2`. It exposes `ServiceProviderConfig`, paginated user listing and user provisioning. Each enabled provider has an independent bearer token. Plaintext is shown once and only its SHA-256 digest is stored. Patch, bulk, group push and password changes are explicitly unsupported.

## Data residency

`data_region` is a routing policy, not proof of physical residency. Compliance requires separate regional PostgreSQL, Redis, object storage, backups, logs, model endpoints and worker queues. Route an organization only after an approved region-change workflow completes export, import and source-deletion verification.

## Quotas, cost and SLA

Tenant quotas cover members, storage, monthly model tokens, cost and alert thresholds. Model usage must be written with `organization_id` and `workspace_id`; unattributed historical usage is intentionally excluded from chargeback.

The monitoring pipeline posts whitelist-only monthly snapshots to `POST /api/v1/enterprise/sla-snapshots`. Tenant operations expose the latest availability, p95 latency, incident count and remaining error budget. Derive these values from production metrics, never browser input.
