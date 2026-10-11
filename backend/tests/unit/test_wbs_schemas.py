import uuid
from decimal import Decimal
from types import SimpleNamespace

from app.schemas.project import ProjectResponse, WBSCodeResponse, WBSCodeUpdate


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
        id=uuid.uuid4(), code="DM", description="Demolition", level="category", parent_id=None, sort_order=0
    )
    assert resp.in_use is False


def wbs_row(code: str, children: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        code=code,
        description=code,
        level="category" if children is not None else "subcategory",
        parent_id=None,
        sort_order=0,
        contract_sum=None,
        children=children or [],
    )


def fake_project(wbs_codes: list) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="P",
        project_number=None,
        client_name="C",
        contractor_name="K",
        contract_sum=Decimal("100.00"),
        gst_rate=Decimal("0.15"),
        end_client_name=None,
        end_client_representative=None,
        end_client_address=None,
        landlord_split_pct=None,
        operator_split_pct=None,
        provisional_sum_total=None,
        retention_tiers=[],
        wbs_codes=wbs_codes,
    )


def test_project_response_marks_in_use_codes_at_every_depth():
    used_child, idle_child = wbs_row("DM.1"), wbs_row("DM.2")
    category = wbs_row("DM", [used_child, idle_child])
    project = fake_project([category, used_child, idle_child])

    dto = ProjectResponse.from_project(project, {used_child.id})

    by_code = {w.code: w for w in dto.wbs_codes}
    assert by_code["DM.1"].in_use is True
    assert by_code["DM.2"].in_use is False
    assert by_code["DM"].in_use is False
    assert {c.code: c.in_use for c in by_code["DM"].children} == {"DM.1": True, "DM.2": False}
    assert not hasattr(used_child, "in_use")


def test_project_response_without_usage_reads_like_the_plain_dto():
    project = fake_project([wbs_row("DM", [wbs_row("DM.1")])])
    plain = ProjectResponse.model_validate(project, from_attributes=True)
    assert ProjectResponse.from_project(project, set()) == plain
