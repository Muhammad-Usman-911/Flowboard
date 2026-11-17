"""One error format for the whole API: {"detail": "...", "code": "..."}.

Services raise these exceptions; `register_exception_handlers` turns them into JSON
responses. Clients (like our React app) can switch on the stable `code` value instead
of parsing human readable messages.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    detail: str = "Bad request"

    def __init__(self, detail: str | None = None, code: str | None = None) -> None:
        self.detail = detail or self.detail
        self.code = code or self.code
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    detail = "Resource not found"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    detail = "Not authenticated"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    detail = "You do not have permission to do this"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    detail = "Conflict"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    detail = "Too many requests, try again later"


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "file_too_large"
    detail = "File is too large"


class UnsupportedMediaTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_file_type"
    detail = "This file type is not allowed"


def _error(status_code: int, detail: str, code: str, **extra: object) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "code": code, **extra})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        response = _error(exc.status_code, exc.detail, exc.code)
        if headers:
            response.headers.update(headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Keep the field level errors (useful for forms) but flatten the message.
        errors = [
            {"field": ".".join(str(p) for p in err["loc"] if p != "body"), "message": err["msg"]}
            for err in exc.errors()
        ]
        first = errors[0] if errors else {"field": "", "message": "Invalid input"}
        detail = f"{first['field']}: {first['message']}" if first["field"] else first["message"]
        return _error(422, detail, "validation_error", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return _error(exc.status_code, str(exc.detail), code)

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        logger.exception("Unhandled error")
        return _error(500, "Internal server error", "internal_error")
