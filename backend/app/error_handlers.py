"""Global exception → HTTP response mapping. Registered once from app.main.

Bodies are FastAPI-native ``{"detail": <str>}``. Repos raise SQLAlchemy errors as-is;
this is the only place that knows which status each one deserves.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    InterfaceError,
    NoResultFound,
    OperationalError,
)
from sqlalchemy.exc import TimeoutError as SATimeoutError

from app.exceptions import AppError

logger = logging.getLogger(__name__)

# Postgres SQLSTATE class 23 = integrity constraint violation.
CONFLICT_SQLSTATES = frozenset({"23505", "23503"})  # unique_violation, foreign_key_violation


def detail_response(
    status_code: int, detail: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


def driver_message(exc: Exception) -> str:
    """First line of the DB driver's message — never ``str(exc)``, which SQLAlchemy pads
    with the SQL statement and bound parameters."""
    orig = getattr(exc, "orig", None)
    source = orig if orig is not None else exc
    lines = str(source).splitlines()
    return lines[0] if lines else type(source).__name__


def sqlstate(exc: Exception) -> str | None:
    orig = getattr(exc, "orig", None)
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return detail_response(exc.status_code, exc.detail, exc.headers)


async def handle_integrity_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, IntegrityError)
    status = 409 if sqlstate(exc) in CONFLICT_SQLSTATES else 400
    message = driver_message(exc)
    logger.warning(
        "DB %s (sqlstate=%s) on %s %s: %s",
        type(exc).__name__,
        sqlstate(exc),
        request.method,
        request.url.path,
        message,
    )
    return detail_response(status, message)


async def handle_data_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DataError)
    message = driver_message(exc)
    logger.warning(
        "DB %s (sqlstate=%s) on %s %s: %s",
        type(exc).__name__,
        sqlstate(exc),
        request.method,
        request.url.path,
        message,
    )
    return detail_response(400, message)


async def handle_no_result(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, NoResultFound)
    return detail_response(404, "Resource not found")


async def handle_db_unavailable(request: Request, exc: Exception) -> JSONResponse:
    message = driver_message(exc)
    logger.error(
        "Database unavailable (%s, sqlstate=%s) on %s %s: %s",
        type(getattr(exc, "orig", exc)).__name__,
        sqlstate(exc),
        request.method,
        request.url.path,
        message,
        exc_info=exc,
    )
    return detail_response(503, message)


async def handle_upstream_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, httpx.HTTPStatusError)
    status = exc.response.status_code
    logger.error(
        "Upstream %s returned %s on %s %s",
        exc.request.url.host,
        status,
        request.method,
        request.url.path,
    )
    return detail_response(502, f"Upstream service error ({status})")


async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return detail_response(500, "Internal server error")


def register(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(IntegrityError, handle_integrity_error)
    app.add_exception_handler(DataError, handle_data_error)
    app.add_exception_handler(NoResultFound, handle_no_result)
    app.add_exception_handler(OperationalError, handle_db_unavailable)
    app.add_exception_handler(InterfaceError, handle_db_unavailable)
    app.add_exception_handler(SATimeoutError, handle_db_unavailable)
    app.add_exception_handler(httpx.HTTPStatusError, handle_upstream_error)
    app.add_exception_handler(Exception, handle_unexpected)
