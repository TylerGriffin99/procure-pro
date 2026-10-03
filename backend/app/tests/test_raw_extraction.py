import uuid

import pytest
from unittest.mock import patch

from app.harness.executors.raw_extraction import execute_raw_extraction
from app.tests.conftest import create_test_document


@pytest.mark.asyncio
async def test_extract_from_valid_pdf(db_session, test_user, test_project):
    doc = await create_test_document(db_session, test_project)
    await db_session.flush()

    mock_pages = [
        type("Page", (), {
            "page_number": 1,
            "extract_text": lambda self: "Claim No. 5\nPeriod From: 01/01/25\nPeriod To: 31/01/25",
            "extract_tables": lambda self: [
                ["Ref", "Description", "Contract Value", "%", "PTD", "Previous", "Current", "Balance"],
                ["1001", "Excavation", "100,000.00", "50.00", "50,000.00", "30,000.00", "20,000.00", "50,000.00"],
            ],
        })(),
    ]

    mock_pdf = type("PDF", (), {
        "pages": mock_pages,
        "__enter__": lambda self: self,
        "__exit__": lambda self, *a: None,
    })()

    with patch("app.harness.executors.raw_extraction.pdfplumber.open", return_value=mock_pdf):
        result = await execute_raw_extraction(
            db=db_session,
            session_id=test_user.id,
            user_id=test_user.id,
            project_id=test_project.id,
            config={"document_id": str(doc.id)},
        )

    assert "pages" in result
    assert len(result["pages"]) == 1
    assert "text" in result["pages"][0]
    assert "tables" in result["pages"][0]
    assert "Claim No. 5" in result["pages"][0]["text"]


@pytest.mark.asyncio
async def test_extract_missing_document(db_session, test_user, test_project):
    with pytest.raises(FileNotFoundError):
        await execute_raw_extraction(
            db=db_session,
            session_id=test_user.id,
            user_id=test_user.id,
            project_id=test_project.id,
            config={"document_id": str(uuid.uuid4())},
        )
