"""Small production observability layer with no external telemetry dependency."""
from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from threading import Lock

from fastapi import FastAPI, Request

SECRET_PATTERN = re.compile(
    r"(?i)(authorization|token|secret|password|cookie|api[_-]?key)([\"'=:\s]+)([^\s,;\"}]+)"
)


def redact(value: object) -> str:
    text = str(value)
    text = re.sub(r"(?i)bearer\s+[a-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class Metrics:
    BUCKETS = (.05, .1, .25, .5, 1, 2, 5)
    def __init__(self):
        self.lock = Lock()
        self.requests = defaultdict(int)
        self.duration = defaultdict(float)
        self.duration_buckets = defaultdict(int)
        self.in_flight = 0

    def begin(self):
        with self.lock:
            self.in_flight += 1

    def finish(self, method: str, route: str, status: int, elapsed: float):
        key = (method, route, str(status))
        with self.lock:
            self.in_flight -= 1
            self.requests[key] += 1
            self.duration[key] += elapsed
            for bound in self.BUCKETS:
                if elapsed <= bound:
                    self.duration_buckets[(*key, bound)] += 1

    def render(self) -> str:
        lines = [
            "# HELP infopulse_http_requests_total Completed HTTP requests.",
            "# TYPE infopulse_http_requests_total counter",
        ]
        with self.lock:
            for key in sorted(self.requests):
                method, route, status = key
                labels = f'method="{method}",route="{route}",status="{status}"'
                lines.append(f"infopulse_http_requests_total{{{labels}}} {self.requests[key]}")
            lines.extend([
                "# HELP infopulse_http_request_duration_seconds_total Cumulative request time.",
                "# TYPE infopulse_http_request_duration_seconds_total counter",
            ])
            for key in sorted(self.duration):
                method, route, status = key
                labels = f'method="{method}",route="{route}",status="{status}"'
                lines.append(f"infopulse_http_request_duration_seconds_total{{{labels}}} {self.duration[key]:.6f}")
            lines.extend([
                "# HELP infopulse_http_request_duration_seconds Request duration distribution.",
                "# TYPE infopulse_http_request_duration_seconds histogram",
            ])
            for key in sorted(self.requests):
                method, route, status = key
                labels = f'method="{method}",route="{route}",status="{status}"'
                for bound in self.BUCKETS:
                    count = self.duration_buckets[(*key, bound)]
                    lines.append(f'infopulse_http_request_duration_seconds_bucket{{{labels},le="{bound}"}} {count}')
                lines.append(f'infopulse_http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {self.requests[key]}')
                lines.append(f"infopulse_http_request_duration_seconds_sum{{{labels}}} {self.duration[key]:.6f}")
                lines.append(f"infopulse_http_request_duration_seconds_count{{{labels}}} {self.requests[key]}")
            lines.extend([
                "# HELP infopulse_http_requests_in_flight Current HTTP requests.",
                "# TYPE infopulse_http_requests_in_flight gauge",
                f"infopulse_http_requests_in_flight {self.in_flight}",
            ])
        return "\n".join(lines) + "\n"


metrics = Metrics()
logger = logging.getLogger("infopulse.request")


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def setup_observability(app: FastAPI) -> None:
    configure_logging()

    @app.middleware("http")
    async def observe(request: Request, call_next):
        start = time.perf_counter()
        metrics.begin()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            route = getattr(request.scope.get("route"), "path", request.url.path)
            metrics.finish(request.method, route, status, elapsed)
            logger.info(
                "request completed",
                extra={
                    "request_id": getattr(request.state, "diagnostic_id", ""),
                    "method": request.method,
                    "path": route,
                    "status_code": status,
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
