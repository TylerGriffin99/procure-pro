import uuid
from decimal import Decimal

from app.schemas.project import WBSCodeUpdate, WBSCodeResponse


def test_wbs_code_update_partial():
    """WBSCodeUpdate should accept partial fields."""
    update = WBSCodeUpdate(contract_sum=Decimal("50000.00"))
    assert update.contract_sum == Decimal("50000.00")
    assert update.code is None
    assert update.description is None


def test_wbs_code_update_all_fields():
    update = WBSCodeUpdate(
        code="NEW",
        description="New desc",
        level="category",
        parent_id=None,
        sort_order=5,
        contract_sum=Decimal("100.00"),
    )
    assert update.code == "NEW"
    assert update.level == "category"


def test_wbs_code_response_has_in_use():
    resp = WBSCodeResponse(
        id=uuid.uuid4(),
        code="DM",
        description="Demolition",
        level="category",
        parent_id=None,
        sort_order=0,
        contract_sum=None,
        in_use=True,
    )
    assert resp.in_use is True


def test_wbs_code_response_in_use_defaults_false():
    resp = WBSCodeResponse(
        id=uuid.uuid4(),
        code="DM",
        description="Demolition",
        level="category",
        parent_id=None,
        sort_order=0,
    )
    assert resp.in_use is False
