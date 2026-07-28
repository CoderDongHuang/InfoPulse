"""Dependency-free concurrent smoke load test for deployed read endpoints."""
from __future__ import annotations
import argparse
import asyncio
import statistics
import time
import httpx


async def run(base_url: str, requests: int, concurrency: int):
    semaphore = asyncio.Semaphore(concurrency)
    durations = []
    failures = 0
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        async def one():
            nonlocal failures
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get("/api/v1/health/live")
                    if response.status_code != 200:
                        failures += 1
                except httpx.HTTPError:
                    failures += 1
                durations.append((time.perf_counter() - started) * 1000)
        await asyncio.gather(*(one() for _ in range(requests)))
    ordered = sorted(durations)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * .95))]
    return {"requests": requests, "failures": failures, "mean_ms": statistics.mean(durations), "p95_ms": p95}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--max-p95-ms", type=float, default=500)
    args = parser.parse_args()
    result = asyncio.run(run(args.base_url, args.requests, args.concurrency))
    print(result)
    raise SystemExit(1 if result["failures"] or result["p95_ms"] > args.max_p95_ms else 0)


if __name__ == "__main__":
    main()
