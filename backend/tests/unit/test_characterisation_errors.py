"""Characterisation: pins today's error classification, defects included.

Each test asserts current behaviour so the refactor that applies a decision flips one assertion.
"""

import uuid
from io import BytesIO

import pytest
from fastapi import Depends, FastAPI, UploadFile
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError
from starlette.datastructures import Headers

from app.database import get_db
from app.dependencies import get_current_user
from app.error_handlers import register
from app.exceptions import BadRequestError
from app.harness.engine import describe_error
from app.harness.models import PhaseDefinition, PhaseType
from app.harness.phase_context import build_phase_context, render_system_prompt
from app.models.user import User
from app.schemas.claim import ClaimCreate, ClaimLineItemCreate
from app.schemas.project import WBSCodeCreate
from app.services import claim_service, project_service
from app.utils.auth import create_access_token

PROJECT_ID = uuid.uuid4()


def _user() -> User:
    return User(id=uuid.uuid4())


def _pdf_upload() -> UploadFile:
    return UploadFile(
        file=BytesIO(b"%PDF-1.4 bytes"), filename="c.pdf", headers=Headers({"content-type": "application/pdf"})
    )


def _bogus_claim() -> ClaimCreate:
    item = ClaimLineItemCreate(
        description="x", item_type="bogus", contract_value=0, percentage=0, ptd=0, previous=0, current=0, balance=0
    )
    return ClaimCreate(claim_number=1, line_items=[item])


def _bogus_wbs() -> WBSCodeCreate:
    return WBSCodeCreate(code="X", description="x", level="bogus")


async def _no_existing_wbs(db, project_id):
    return []


async def _any_project(db, project_id):
    return object()


def _raise_os_error(content: bytes) -> str:
    raise OSError("disk read failed")


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

    @app.get("/wbs")
    async def wbs():
        await project_service.create_wbs_code(None, PROJECT_ID, _bogus_wbs(), _user())  # type: ignore[arg-type]

    @app.get("/claim")
    async def claim():
        await claim_service.create_claim(None, PROJECT_ID, _bogus_claim(), _user())  # type: ignore[arg-type]

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
    monkeypatch.setattr(claim_service, "_extract_screenable_text", _raise_os_error)


@pytest.fixture
def empty_wbs_repo(monkeypatch):
    monkeypatch.setattr(project_service.project_repo, "get_by_id", _any_project)
    monkeypatch.setattr(project_service.wbs_code_repo, "get_by_project", _no_existing_wbs)


# --- non-PDF fault during upload screening (D: 400 -> 500 for non-parser faults) ---


async def test_upload_non_parser_fault_today_is_bad_request(unreadable_pdf):
    with pytest.raises(BadRequestError) as exc_info:
        await claim_service.create_document_from_upload(None, PROJECT_ID, _pdf_upload())  # type: ignore[arg-type]
    assert exc_info.value.detail == "Could not read the PDF to screen it"


async def test_upload_non_parser_fault_today_returns_400(client, unreadable_pdf):
    resp = await client.get("/upload")
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Could not read the PDF to screen it"}


# --- malformed token sub (D: 500 -> 401) ---


async def test_malformed_sub_today_raises_value_error():
    token = create_access_token({"sub": "not-a-uuid"})
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        await get_current_user(token, None)  # type: ignore[arg-type]


async def test_malformed_sub_today_returns_500(client, caplog):
    token = create_access_token({"sub": "not-a-uuid"})
    resp = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert _unhandled_cause(caplog) is ValueError


# --- invalid WBS level (D: 500 -> 422) ---


def test_wbs_schema_today_accepts_any_level():
    assert _bogus_wbs().level == "bogus"


async def test_wbs_invalid_level_today_raises_value_error(empty_wbs_repo):
    with pytest.raises(ValueError, match="'bogus' is not a valid WBSLevel"):
        await project_service.create_wbs_code(None, PROJECT_ID, _bogus_wbs(), _user())  # type: ignore[arg-type]


async def test_wbs_invalid_level_today_returns_500(client, caplog, empty_wbs_repo):
    resp = await client.get("/wbs")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert _unhandled_cause(caplog) is ValueError


# --- invalid claim line item type (D: 500 -> 422) ---


def test_claim_line_item_schema_today_accepts_any_item_type():
    assert _bogus_claim().line_items[0].item_type == "bogus"


async def test_claim_invalid_item_type_today_raises_value_error():
    with pytest.raises(ValueError, match="'bogus' is not a valid ClaimItemType"):
        await claim_service.create_claim(None, PROJECT_ID, _bogus_claim(), _user())  # type: ignore[arg-type]


async def test_claim_invalid_item_type_today_returns_500(client, caplog):
    resp = await client.get("/claim")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert _unhandled_cause(caplog) is ValueError


# --- describe_error echoes the SQL statement (D2 flips to absent) ---


def test_describe_error_today_echoes_sql_statement():
    text = describe_error(OperationalError("SELECT 1", {}, Exception("conn refused")))
    assert text.startswith("OperationalError: (builtins.Exception) conn refused")
    assert "SELECT 1" in text


# --- phase context fallback (D7 flips to pytest.raises) ---


async def _missing_file(db, session_id, path):
    return None


async def test_phase_context_today_substitutes_file_not_found(monkeypatch):
    monkeypatch.setattr("app.harness.phase_context.harness_repo.read_workspace_file", _missing_file)
    phase = PhaseDefinition(
        name="match",
        description="Reads a missing input",
        phase_type=PhaseType.LLM_SINGLE,
        workspace_output="out.json",
        system_prompt_template="Items: $workspace_parsed_claim",
        workspace_inputs=["parsed_claim.json"],
    )
    ctx = await build_phase_context(db=None, session_id="s", project_id="p", phase_def=phase)
    assert ctx["workspace_parsed_claim"] == "FILE NOT FOUND"
    assert render_system_prompt(phase, ctx) == "Items: FILE NOT FOUND"
