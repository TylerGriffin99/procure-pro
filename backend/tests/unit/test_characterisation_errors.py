"""Characterisation: pins today's error classification, defects included.

Each test asserts current behaviour so the refactor that applies a decision flips one assertion.
"""

import uuid
from io import BytesIO

import pytest
from fastapi import Depends, FastAPI, UploadFile
from httpx import ASGITransport, AsyncClient
from pdfplumber.utils.exceptions import PdfminerException
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from starlette.datastructures import Headers

from app.database import get_db
from app.dependencies import get_current_user
from app.error_handlers import register
from app.exceptions import BadRequestError, NotFoundError, UnauthorizedError
from app.harness.engine import describe_error
from app.models.user import User
from app.schemas.claim import ClaimCreate, ClaimLineItemCreate
from app.schemas.project import WBSCodeCreate
from app.services import claim_service, guardrails, project_service
from app.utils.auth import create_access_token

PROJECT_ID = uuid.uuid4()


def _user() -> User:
    return User(id=uuid.uuid4())


def _pdf_upload() -> UploadFile:
    return UploadFile(
        file=BytesIO(b"%PDF-1.4 bytes"), filename="c.pdf", headers=Headers({"content-type": "application/pdf"})
    )


BOGUS_CLAIM_LINE_ITEM = {
    "description": "x",
    "item_type": "bogus",
    "contract_value": 0,
    "percentage": 0,
    "ptd": 0,
    "previous": 0,
    "current": 0,
    "balance": 0,
}
BOGUS_CLAIM = {"claim_number": 1, "line_items": [BOGUS_CLAIM_LINE_ITEM]}
BOGUS_WBS = {"code": "X", "description": "x", "level": "bogus"}


async def _no_existing_wbs(db, project_id):
    return []


async def _any_project(db, project_id):
    return object()


def _raise_os_error(content: bytes) -> str:
    raise OSError("disk read failed")


def _raise_memory_error(content: bytes) -> str:
    raise MemoryError


def _raise_parser_error(content: bytes) -> str:
    raise PdfminerException("No /Root object! - Is this really a PDF?")


def _raise_zero_pages(content: bytes) -> str:
    raise ValueError("PDF has zero pages")


def build_app() -> FastAPI:
    app = FastAPI()
    register(app)

    async def no_db():
        yield None

    app.dependency_overrides[get_db] = no_db

    @app.get("/upload")
    async def upload():
        await claim_service.create_document_from_upload(None, PROJECT_ID, _pdf_upload())  # type: ignore[arg-type]

    @app.get("/me")
    async def me(user: User = Depends(get_current_user)):
        return {"id": str(user.id)}

    @app.post("/wbs")
    async def wbs(body: WBSCodeCreate):
        await project_service.create_wbs_code(None, PROJECT_ID, body, _user())  # type: ignore[arg-type]

    @app.post("/claim")
    async def claim(body: ClaimCreate):
        await claim_service.create_claim(None, PROJECT_ID, body, _user())  # type: ignore[arg-type]

    return app


def _unhandled_cause(caplog: pytest.LogCaptureFixture) -> type[BaseException] | None:
    record = next(r for r in caplog.records if r.getMessage().startswith("Unhandled error"))
    return record.exc_info[0] if record.exc_info else None


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=build_app(), raise_app_exceptions=False), base_url="http://t"
    ) as c:
        yield c


@pytest.fixture
def unreadable_pdf(monkeypatch):
    monkeypatch.setattr(guardrails, "extract_screenable_text", _raise_os_error)


@pytest.fixture
def empty_wbs_repo(monkeypatch):
    monkeypatch.setattr(project_service.project_repo, "get_by_id", _any_project)
    monkeypatch.setattr(project_service.wbs_code_repo, "get_by_project", _no_existing_wbs)


# --- non-PDF fault during upload screening (D13 applied: 400 -> 500 for non-parser faults) ---


async def test_upload_non_parser_fault_propagates(unreadable_pdf):
    with pytest.raises(OSError, match="disk read failed"):
        await claim_service.create_document_from_upload(None, PROJECT_ID, _pdf_upload())  # type: ignore[arg-type]


async def test_upload_non_parser_fault_returns_500(client, unreadable_pdf, caplog):
    resp = await client.get("/upload")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert _unhandled_cause(caplog) is OSError


async def test_upload_memory_error_returns_500(client, monkeypatch, caplog):
    monkeypatch.setattr(guardrails, "extract_screenable_text", _raise_memory_error)
    resp = await client.get("/upload")
    assert resp.status_code == 500
    assert _unhandled_cause(caplog) is MemoryError


@pytest.mark.parametrize("parser_fault", [_raise_parser_error, _raise_zero_pages])
async def test_upload_parser_fault_returns_400(client, monkeypatch, parser_fault):
    monkeypatch.setattr(guardrails, "extract_screenable_text", parser_fault)
    resp = await client.get("/upload")
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Could not read the PDF to screen it"}


# --- malformed token sub (D12 applied: 500 -> 401) ---


async def test_malformed_sub_raises_unauthorized():
    token = create_access_token({"sub": "not-a-uuid"})
    with pytest.raises(UnauthorizedError, match="Invalid token"):
        await get_current_user(token, None)  # type: ignore[arg-type]


async def test_malformed_sub_returns_401(client):
    token = create_access_token({"sub": "not-a-uuid"})
    resp = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid token"}


# --- invalid WBS level (D12 applied: 500 -> 422) ---


def test_wbs_schema_rejects_unknown_level():
    with pytest.raises(ValidationError, match="level"):
        WBSCodeCreate.model_validate(BOGUS_WBS)


async def test_wbs_invalid_level_returns_422(client, empty_wbs_repo):
    resp = await client.post("/wbs", json=BOGUS_WBS)
    assert resp.status_code == 422


# --- invalid claim line item type (D12 applied: 500 -> 422) ---


def test_claim_line_item_schema_rejects_unknown_item_type():
    with pytest.raises(ValidationError, match="item_type"):
        ClaimLineItemCreate.model_validate(BOGUS_CLAIM_LINE_ITEM)


async def test_claim_invalid_item_type_returns_422(client):
    resp = await client.post("/claim", json=BOGUS_CLAIM)
    assert resp.status_code == 422


# --- describe_error (D2 applied: type name only; AppError adds its safe detail) ---


def test_describe_error_omits_sql_statement_and_driver_text():
    assert describe_error(OperationalError("SELECT 1", {}, Exception("conn refused"))) == "OperationalError"


def test_describe_error_keeps_app_error_detail():
    assert describe_error(NotFoundError("Claim not found")) == "NotFoundError: Claim not found"
