"""Verify item count validation catches LLM response mismatches."""
import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.executors.create_records import execute_create_records
from app.repos import harness_repo


def _parsed_claim(items: list[dict]) -> str:
    return json.dumps({
        "metadata": {"claim_number": "1"},
        "line_items": items,
        "summary": {
            "original_contract_total": "100000.00",
            "revised_contract_total": "100000.00",
        },
    })


def _contract_item(idx: int, ref: str = "", desc: str = "Item", value: str = "10000.00") -> dict:
    return {
        "item_index": idx,
        "ref_code": ref,
        "description": desc,
        "item_type": "contract_work",
        "contract_value": value,
        "percentage": "0.00",
        "ptd": "0.00",
        "previous": "0.00",
        "current": "0.00",
        "balance": value,
    }


def _variation_item(idx: int, desc: str = "Var", value: str = "5000.00") -> dict:
    return {
        "item_index": idx,
        "ref_code": "",
        "description": desc,
        "item_type": "variation",
        "contract_value": value,
        "percentage": "0.00",
        "ptd": "0.00",
        "previous": "0.00",
        "current": "0.00",
        "balance": value,
    }


@pytest.mark.asyncio
async def test_wbs_count_mismatch_raises(
    db_session: AsyncSession, test_user, test_project, test_document,
):
    """WBS matches returning fewer items than contract_work items should fail."""
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )

    items = [_contract_item(0, desc="Excavation"), _contract_item(1, desc="Concrete")]
    await harness_repo.write_workspace_file(
        db_session, session.id, "parsed_claim.json", _parsed_claim(items),
    )
    # WBS matches only has 1 item instead of 2
    await harness_repo.write_workspace_file(
        db_session, session.id, "wbs_matches.json",
        json.dumps([{"item_index": 0, "wbs_code": "EX-01", "wbs_code_id": None, "wbs_description": "Excavation", "parent_code": "EX", "is_new": False, "confidence": 0.9}]),
    )
    await harness_repo.write_workspace_file(
        db_session, session.id, "vps_matches.json", json.dumps([]),
    )
    await db_session.flush()

    with pytest.raises(ValueError, match="WBS categorisation returned 1 contract_work matches but extraction has 2 contract_work items"):
        await execute_create_records(
            db_session, session.id, test_user.id, test_project.id, {},
        )


@pytest.mark.asyncio
async def test_vps_count_mismatch_raises(
    db_session: AsyncSession, test_user, test_project, test_document,
):
    """VPS matches returning wrong count should fail."""
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )

    items = [_contract_item(0), _variation_item(1, desc="Extra work")]
    await harness_repo.write_workspace_file(
        db_session, session.id, "parsed_claim.json", _parsed_claim(items),
    )
    await harness_repo.write_workspace_file(
        db_session, session.id, "wbs_matches.json",
        json.dumps([{"item_index": 0, "wbs_code": "EX-01", "wbs_code_id": None, "wbs_description": "Item", "parent_code": "EX", "is_new": False, "confidence": 0.9}]),
    )
    # VPS matches empty but there's 1 variation
    await harness_repo.write_workspace_file(
        db_session, session.id, "vps_matches.json", json.dumps([]),
    )
    await db_session.flush()

    with pytest.raises(ValueError, match="VPS matching returned 0 variation/PS matches but extraction has 1 variation/provisional_sum items"):
        await execute_create_records(
            db_session, session.id, test_user.id, test_project.id, {},
        )


@pytest.mark.asyncio
async def test_out_of_range_item_index_raises(
    db_session: AsyncSession, test_user, test_project, test_document,
):
    """An item_index outside the line_items range should fail."""
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )

    items = [_contract_item(0)]
    await harness_repo.write_workspace_file(
        db_session, session.id, "parsed_claim.json", _parsed_claim(items),
    )
    # item_index 99 is out of range
    await harness_repo.write_workspace_file(
        db_session, session.id, "wbs_matches.json",
        json.dumps([{"item_index": 99, "wbs_code": "EX-01", "wbs_code_id": None, "wbs_description": "Item", "parent_code": "EX", "is_new": False, "confidence": 0.9}]),
    )
    await harness_repo.write_workspace_file(
        db_session, session.id, "vps_matches.json", json.dumps([]),
    )
    await db_session.flush()

    with pytest.raises(ValueError, match="out-of-range item_index"):
        await execute_create_records(
            db_session, session.id, test_user.id, test_project.id, {},
        )
