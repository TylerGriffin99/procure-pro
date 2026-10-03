import json
import uuid
import pytest
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.executors.validate_claim import execute_validate_claim
from app.models.claim_parse_flag import FlagType, FlagSeverity
from app.repos import harness_repo


def _make_parsed_claim_json(
    line_items: list[dict] | None = None,
    summary: dict | None = None,
) -> str:
    default_items = [
        {
            "ref_code": "1001",
            "description": "Excavation",
            "item_type": "contract_work",
            "contract_value": "100000.00",
            "percentage": "50.00",
            "ptd": "50000.00",
            "previous": "30000.00",
            "current": "20000.00",
            "balance": "50000.00",
        },
    ]
    default_summary = {
        "original_contract_total": "100000.00",
        "variations_total": "0.00",
        "revised_contract_total": "100000.00",
        "claimed_amount": "50000.00",
    }
    return json.dumps({
        "metadata": {"claim_number": "1"},
        "line_items": line_items or default_items,
        "summary": summary or default_summary,
    })


@pytest.mark.asyncio
async def test_valid_claim_no_flags(db_session: AsyncSession, test_user, test_project, test_document):
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )
    await harness_repo.write_workspace_file(
        db_session, session.id, "parsed_claim.json", _make_parsed_claim_json(),
    )

    result = await execute_validate_claim(
        db=db_session, session_id=session.id,
        user_id=test_user.id, project_id=test_project.id, config={},
    )

    flags = await harness_repo.list_flags_by_session(db_session, session.id)
    assert len(flags) == 0
    assert result["total_items"] == 1


@pytest.mark.asyncio
async def test_over_claim_flagged(db_session: AsyncSession, test_user, test_project, test_document):
    items = [{
        "ref_code": "1001",
        "description": "Excavation",
        "item_type": "contract_work",
        "contract_value": "100000.00",
        "percentage": "120.00",
        "ptd": "120000.00",
        "previous": "0.00",
        "current": "120000.00",
        "balance": "-20000.00",
    }]
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )
    await harness_repo.write_workspace_file(
        db_session, session.id, "parsed_claim.json",
        _make_parsed_claim_json(line_items=items),
    )

    await execute_validate_claim(
        db=db_session, session_id=session.id,
        user_id=test_user.id, project_id=test_project.id, config={},
    )

    flags = await harness_repo.list_flags_by_session(db_session, session.id)
    over_claims = [f for f in flags if f.flag_type == FlagType.over_claim]
    pct_errors = [f for f in flags if f.flag_type == FlagType.percentage_error]
    assert len(over_claims) >= 1
    assert len(pct_errors) >= 1


@pytest.mark.asyncio
async def test_project_over_budget_flagged(db_session: AsyncSession, test_user, test_project, test_document):
    items = [
        {
            "ref_code": "1001",
            "description": "Excavation",
            "item_type": "contract_work",
            "contract_value": "100000.00",
            "percentage": "50.00",
            "ptd": "50000.00",
            "previous": "0.00",
            "current": "50000.00",
            "balance": "50000.00",
        },
        {
            "ref_code": "V001",
            "description": "Extra drainage",
            "item_type": "variation",
            "contract_value": "25000.00",
            "percentage": "0.00",
            "ptd": "0.00",
            "previous": "0.00",
            "current": "0.00",
            "balance": "25000.00",
        },
    ]
    summary = {
        "original_contract_total": "100000.00",
        "variations_total": "25000.00",
        "revised_contract_total": "125000.00",
        "claimed_amount": "50000.00",
    }
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )
    await harness_repo.write_workspace_file(
        db_session, session.id, "parsed_claim.json",
        _make_parsed_claim_json(line_items=items, summary=summary),
    )

    await execute_validate_claim(
        db=db_session, session_id=session.id,
        user_id=test_user.id, project_id=test_project.id, config={},
    )

    flags = await harness_repo.list_flags_by_session(db_session, session.id)
    over_budget = [f for f in flags if f.flag_type == FlagType.project_over_budget]
    assert len(over_budget) >= 1


@pytest.mark.asyncio
async def test_duplicate_refs_flagged(db_session: AsyncSession, test_user, test_project, test_document):
    items = [
        {
            "ref_code": "1001", "description": "Excavation", "item_type": "contract_work",
            "contract_value": "50000.00", "percentage": "0.00", "ptd": "0.00",
            "previous": "0.00", "current": "0.00", "balance": "50000.00",
        },
        {
            "ref_code": "1001", "description": "Also Excavation", "item_type": "contract_work",
            "contract_value": "50000.00", "percentage": "0.00", "ptd": "0.00",
            "previous": "0.00", "current": "0.00", "balance": "50000.00",
        },
    ]
    summary = {
        "original_contract_total": "100000.00",
        "variations_total": "0.00",
        "revised_contract_total": "100000.00",
        "claimed_amount": "0.00",
    }
    session = await harness_repo.create_session(
        document_id=test_document.id,
        db=db_session, user_id=test_user.id,
        project_id=test_project.id, harness_type="claim_parse",
    )
    await harness_repo.write_workspace_file(
        db_session, session.id, "parsed_claim.json",
        _make_parsed_claim_json(line_items=items, summary=summary),
    )

    await execute_validate_claim(
        db=db_session, session_id=session.id,
        user_id=test_user.id, project_id=test_project.id, config={},
    )

    flags = await harness_repo.list_flags_by_session(db_session, session.id)
    dups = [f for f in flags if f.flag_type == FlagType.duplicate_item]
    assert len(dups) >= 1
