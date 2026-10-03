"""Verify that missing ref_code no longer creates a flag."""
import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.executors.validate_claim import execute_validate_claim
from app.repos import harness_repo


@pytest.mark.asyncio
async def test_missing_ref_code_does_not_create_flag(
    db_session: AsyncSession, test_user, test_project, test_document,
):
    """A line item with empty ref_code should NOT produce a missing_ref flag."""
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session,
        user_id=test_user.id,
        project_id=test_project.id,
        harness_type="claim_parse",
    )

    parsed = {
        "line_items": [
            {
                "item_index": 0,
                "ref_code": "",
                "description": "Suspended ceilings",
                "item_type": "contract_work",
                "contract_value": "50000.00",
                "percentage": "40.00",
                "ptd": "20000.00",
                "previous": "10000.00",
                "current": "10000.00",
                "balance": "30000.00",
            }
        ],
        "summary": {},
    }
    await harness_repo.write_workspace_file(
        db_session, session.id, "parsed_claim.json", json.dumps(parsed),
    )
    await db_session.flush()

    result = await execute_validate_claim(
        db_session, session.id, test_user.id, test_project.id, {},
    )

    flags = await harness_repo.list_flags_by_session(db_session, session.id)
    flag_types = [f.flag_type.value for f in flags]
    assert "missing_ref" not in flag_types
    assert result["flags_created"] == 0
