# Performance Baseline

Date: 2026-07-29  
Target: `GET /api/v1/health/live` on the local release candidate  
Environment: Windows development host, one Uvicorn process, SQLite drill database

| Requests | Concurrency | Failures | Mean | p95 | Result |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1,000 | 25 | 0 | 204 ms | 410 ms | Pass against 500 ms gate |
| 1,000 | 50 | 0 | 437 ms | 650 ms | Capacity observation; above current latency gate |

The release gate baseline is 1,000 requests at concurrency 25 with zero failures and p95 below 500 ms. The concurrency 50 result is retained rather than discarded: it indicates the next capacity work should evaluate multiple Uvicorn workers, horizontal replicas and asynchronous log shipping before raising the supported profile.

This local probe is not a substitute for a production-like test. Before public launch, repeat the authenticated search, event list, dashboard and BI read paths against PostgreSQL and Redis using representative data volume, then attach those results to the release approval.
