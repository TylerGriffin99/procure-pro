"""Domain errors. Services raise these; routers never do; error_handlers maps them to HTTP.

The status code lives on the class so the service layer expresses *what* went wrong
(not found, conflict, …) and never imports anything from FastAPI.
"""

from typing import ClassVar


class AppError(Exception):
    status_code: int = 500
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class BadRequestError(AppError):
    status_code = 400


class UnauthorizedError(AppError):
    status_code = 401
    headers: ClassVar[dict[str, str] | None] = {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class UnprocessableError(AppError):
    status_code = 422


class ExternalServiceError(AppError):
    status_code = 502


class InternalError(AppError):
    status_code = 500


def require[T](value: T | None, what: str) -> T:
    if value is None:
        raise NotFoundError(f"{what} not found")
    return value


def reloaded[T](value: T | None, what: str) -> T:
    """For a re-read of a row this request just wrote: ``None`` is an invariant violation (500), not a 404."""
    if value is None:
        raise InternalError(f"{what} vanished after commit")
    return value
