import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import DataError, IntegrityError, NoResultFound, OperationalError

from app.error_handlers import register
from app.exceptions import ConflictError, NotFoundError, UnauthorizedError


class FakePgError(Exception):
    def __init__(self, message: str, sqlstate: str | None) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate


def build_app() -> FastAPI:
    app = FastAPI()
    register(app)

    @app.get("/not-found")
    async def not_found():
        raise NotFoundError("Claim not found")

    @app.get("/conflict")
    async def conflict():
        raise ConflictError("Only failed sessions can be re-run")

    @app.get("/unauthorized")
    async def unauthorized():
        raise UnauthorizedError("Invalid token")

    @app.get("/unique")
    async def unique():
        orig = FakePgError('duplicate key value violates unique constraint "uq_claim"\nDETAIL: Key (x)=(1) exists.', "23505")
        raise IntegrityError("INSERT INTO claims (secret) VALUES (?)", {"secret": "s3cr3t"}, orig)

    @app.get("/fk")
    async def fk():
        raise IntegrityError("stmt", {}, FakePgError("violates foreign key constraint", "23503"))

    @app.get("/not-null")
    async def not_null():
        raise IntegrityError("stmt", {}, FakePgError('null value in column "name"', "23502"))

    @app.get("/integrity-no-sqlstate")
    async def integrity_no_sqlstate():
        raise IntegrityError("stmt", {}, Exception("integrity failed"))

    @app.get("/data")
    async def data():
        raise DataError("stmt", {}, FakePgError("invalid input syntax for type uuid", "22P02"))

    @app.get("/no-result")
    async def no_result():
        raise NoResultFound()

    @app.get("/db-down")
    async def db_down():
        raise OperationalError("stmt", {}, FakePgError("connection refused", None))

    @app.get("/upstream")
    async def upstream():
        req = httpx.Request("POST", "https://jev.test/decisions")
        raise httpx.HTTPStatusError("boom", request=req, response=httpx.Response(402, request=req))

    @app.get("/boom")
    async def boom():
        raise KeyError("database_password=hunter2")

    return app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=build_app(), raise_app_exceptions=False), base_url="http://t"
    ) as c:
        yield c


@pytest.mark.parametrize(
    ("path", "status", "detail"),
    [
        ("/not-found", 404, "Claim not found"),
        ("/conflict", 409, "Only failed sessions can be re-run"),
        ("/unauthorized", 401, "Invalid token"),
        ("/unique", 409, 'duplicate key value violates unique constraint "uq_claim"'),
        ("/fk", 409, "violates foreign key constraint"),
        ("/not-null", 400, 'null value in column "name"'),
        ("/integrity-no-sqlstate", 400, "integrity failed"),
        ("/data", 400, "invalid input syntax for type uuid"),
        ("/no-result", 404, "Resource not found"),
        ("/db-down", 503, "connection refused"),
        ("/upstream", 502, "Upstream service error (402)"),
        ("/boom", 500, "Internal server error"),
    ],
)
async def test_status_and_detail(client, path, status, detail):
    resp = await client.get(path)
    assert resp.status_code == status
    assert resp.json() == {"detail": detail}


async def test_unauthorized_carries_www_authenticate(client):
    resp = await client.get("/unauthorized")
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_db_error_never_echoes_statement_or_params(client):
    body = (await client.get("/unique")).text
    assert "INSERT" not in body and "s3cr3t" not in body and "DETAIL" not in body


async def test_500_never_echoes_exception_message(client):
    body = (await client.get("/boom")).text
    assert "hunter2" not in body and "KeyError" not in body
