import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError, UnauthorizedError

logger = logging.getLogger(__name__)


def _error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    headers = dict(exc.headers or {})
    if isinstance(exc, UnauthorizedError):
        headers.setdefault("WWW-Authenticate", "Bearer")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message),
        headers=headers or None,
    )


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Não devolve "input": o valor enviado pode conter senhas ou dados sensíveis.
    details = [
        {
            "field": ".".join(str(part) for part in err["loc"] if part not in ("body", "query", "path")),
            "message": str(err["msg"]),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_body("validation_error", "Dados inválidos", details),
    )


async def http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body("http_error", str(exc.detail)),
        headers=getattr(exc, "headers", None),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro não tratado em %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=_error_body("internal_error", "Erro interno do servidor"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
