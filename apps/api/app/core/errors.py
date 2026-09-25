from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: Any = None):
        self.code = code
        self.message = message
        self.status = status
        self.details = details


class NotFound(AppError):
    def __init__(self, what: str = "Resource"):
        super().__init__("not_found", f"{what} not found", 404)


class Forbidden(AppError):
    def __init__(self, message: str = "You do not have access to this resource"):
        super().__init__("forbidden", message, 403)


class LimitExceeded(AppError):
    def __init__(self, message: str, details: Any = None):
        super().__init__("limit_exceeded", message, 402, details)


def _body(code: str, message: str, details: Any = None) -> dict:
    """The one error shape every endpoint returns. Never contains stack traces or database messages."""
    return {"success": False,
            "error": {"code": code, "message": message, "details": details, "requestId": request_id_var.get()}}


def error_response(status: int, code: str, message: str, details: Any = None,
                   headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(_body(code, message, details), status_code=status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        request.state.error_code = exc.code
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
                429: "rate_limited"}.get(exc.status_code, "http_error")
        request.state.error_code = code
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        # Field locations and messages only; the rejected input is not echoed back.
        errors = [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]
        request.state.error_code = "validation_error"
        return JSONResponse(_body("validation_error", "Some fields are missing or invalid.", errors),
                            status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        import logging

        from app.core.logging import log

        request.state.error_code = "internal_error"
        log(logging.getLogger("api"), logging.ERROR, "unhandled_error", error_type=type(exc).__name__,
            path=request.url.path, exc_info=True)
        return JSONResponse(_body("internal_error", "Something went wrong on our side. Please try again; if it "
                                  "keeps happening, contact support with the request ID."), status_code=500)
