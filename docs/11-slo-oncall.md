# SLO, Error Budget and On-call

## Objectives

| Signal | 30-day objective | Page condition |
| --- | --- | --- |
| Authenticated API availability | 99.9% | success ratio below 98% for 5 minutes |
| API latency | p95 below 500 ms | p95 above 500 ms for 10 minutes |
| Stable API capacity | at least 2 replicas | fewer than 2 for 2 minutes |
| Scheduler and knowledge workers | at least 1 replica each | unavailable for 5 minutes |
| Scheduled delivery | 99% within 15 minutes | dead-letter growth or two missed intervals |

The 99.9% monthly objective provides roughly 43 minutes of error budget in a 30-day month. When 50% is consumed, stop nonessential releases and review the largest contributors. When 100% is consumed, freeze feature releases until a reliability change restores budget.

## Ownership

- Primary on-call acknowledges pages within 10 minutes.
- Secondary on-call takes ownership after 10 minutes without acknowledgement.
- Data-source failures are isolated from core API incidents unless more than half of enabled sources fail.
- Security, privacy deletion, credential exposure and cross-user access are always P0/P1 regardless of traffic impact.

## Operational reports

Weekly operations review includes SLO attainment, error-budget consumption, source health, task failures, model cost, feedback status, top product routes, canary outcomes and releases. The running application exposes privacy-controlled aggregates under the administrator Product Operations tab.

