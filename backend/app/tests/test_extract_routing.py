"""Tests for Phase 2 format-based routing."""
import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.executors.extract_line_items import execute_extract_line_items
from app.repos import harness_repo


@pytest.mark.asyncio
async def test_wbpro_routes_to_deterministic(db_session: AsyncSession, test_user, test_project, test_document):
    """When format is wbpro, the deterministic parser is used."""
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )

    # Write format detection result
    await harness_repo.write_workspace_file(
        db_session, session.id, "format_detection.json",
        json.dumps({"format": "wbpro", "confidence": 0.99, "markers_found": []}),
    )

    # Write minimal raw extraction with one contract works item
    raw = {
        "metadata": {},
        "pages": [{
            "page_num": 1,
            "text": "CONTRACT WORKS\nClaim No. 1",
            "tables": [[
                ["1.0", "Test Item", "50000.00", "0.00", "0.00", "0.00", "0.00", "50000.00"],
            ]],
        }],
    }
    await harness_repo.write_workspace_file(
        db_session, session.id, "raw_extraction.json", json.dumps(raw),
    )
    await db_session.flush()

    result = await execute_extract_line_items(
        db_session, session.id, test_user.id, test_project.id, {},
    )

    assert len(result["line_items"]) == 1
    assert result["line_items"][0]["description"] == "Test Item"
    assert result["line_items"][0]["item_type"] == "contract_work"


@pytest.mark.asyncio
async def test_generic_routes_to_llm_placeholder(db_session: AsyncSession, test_user, test_project, test_document):
    """When format is generic, a NotImplementedError is raised (LLM fallback not wired yet)."""
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )

    await harness_repo.write_workspace_file(
        db_session, session.id, "format_detection.json",
        json.dumps({"format": "generic", "confidence": 0.5, "markers_found": []}),
    )
    await harness_repo.write_workspace_file(
        db_session, session.id, "raw_extraction.json",
        json.dumps({"metadata": {}, "pages": []}),
    )
    await db_session.flush()

    with pytest.raises(NotImplementedError, match="LLM extraction fallback"):
        await execute_extract_line_items(
            db_session, session.id, test_user.id, test_project.id, {},
        )
