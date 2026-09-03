from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.db import engine
from app.errors import DomainError, ServiceUnavailable
from app.logging import RequestLogMiddleware, configure_logging

configure_logging()

app = FastAPI(
    title="Product Service",
    version="0.1.0",
    description=(
        "Catalogue microservice for products and a hierarchical category tree. "
        "Search lives on GET /api/v1/products — filters combine with AND."
    ),
)
app.add_middleware(RequestLogMiddleware)
app.include_router(api_router)


def _error_body(
    code: str, message: str, details: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or []}}


@app.exception_handler(DomainError)
async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, str(exc), exc.details),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        loc = [str(part) for part in error.get("loc", ()) if part not in {"body", "query", "path"}]
        details.append(
            {
                "field": ".".join(loc) or str(error.get("loc", ())),
                "message": error.get("msg", "invalid"),
            }
        )
    return JSONResponse(
        status_code=422,
        content=_error_body("validation_error", "Request validation failed", details),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, DomainError | RequestValidationError | StarletteHTTPException):
        raise exc
    return JSONResponse(
        status_code=500,
        content=_error_body("internal_error", "An unexpected error occurred"),
    )


@app.get("/health", tags=["ops"], summary="Liveness and database reachability")
async def health() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise ServiceUnavailable("Database is unreachable") from exc
    return {"status": "ok"}
