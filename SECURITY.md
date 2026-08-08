# Security Policy

## Supported Versions

Security fixes are provided for the latest commit on the default branch.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private
vulnerability reporting feature for this repository and include affected
versions, reproduction steps, impact, and any suggested mitigation.

Maintainers should acknowledge a report within 7 days. Disclosure should wait
until a fix or documented mitigation is available.

## Deployment Boundary

InfoPulse is intended for self-hosting. Before exposing it beyond localhost,
replace every placeholder secret, restrict `CORS_ORIGINS` and `TRUSTED_HOSTS`,
run database migrations, and place the API behind TLS and a rate-limiting
reverse proxy. Never commit `.env`, cookies, API keys, uploaded knowledge, or
runtime databases.
