"""Consistent application errors and FastAPI exception handlers."""

import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def diagnostic_id(request: Request) -> str:
    return getattr(request.state, "diagnostic_id", str(uuid.uuid4()))


def error_payload(request: Request, code: str, message: str, details: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details, "diagnostic_id": diagnostic_id(request)}}


def setup_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def attach_diagnostic_id(request: Request, call_next):
        request.state.diagnostic_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.diagnostic_id
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(content=error_payload(request, exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"], "type": item["type"]}
            for item in exc.errors()
        ]
        return JSONResponse(content=error_payload(request, "VALIDATION_ERROR", "请求参数不符合要求", details), status_code=422)

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException):
        code_by_status = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 429: "RATE_LIMITED"}
        message = exc.detail if isinstance(exc.detail, str) else "请求处理失败"
        details = None if isinstance(exc.detail, str) else exc.detail
        return JSONResponse(
            content=error_payload(request, code_by_status.get(exc.status_code, "HTTP_ERROR"), message, details),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        request_id = diagnostic_id(request)
        logger.exception("Unhandled API error diagnostic_id=%s", request_id, exc_info=exc)
        return JSONResponse(content=error_payload(request, "INTERNAL_ERROR", "服务暂时无法处理请求"), status_code=500)
