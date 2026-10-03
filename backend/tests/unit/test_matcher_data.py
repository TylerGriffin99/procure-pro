import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.harness.matchers.data import Subcat, VpsRecord, vps_records, wbs_subcategories
from app.models.wbs_code import WBSLevel


@pytest.mark.asyncio
async def test_wbs_subcategories_filters_and_derives_parent_code(monkeypatch):
    cat_id, orphan_id = uuid.uuid4(), uuid.uuid4()
    rows = [
        SimpleNamespace(id=cat_id, code="DM", level=WBSLevel.category,
                        description="Demolition", parent_id=None, contract_sum=None),
        SimpleNamespace(id=orphan_id, code="XX-01", level=WBSLevel.subcategory,
                        description=None, parent_id=None, contract_sum=None),
        SimpleNamespace(id=uuid.UUID(int=2), code="DM-01", level=WBSLevel.subcategory,
                        description="Soft strip", parent_id=cat_id,
                        contract_sum=Decimal("12345.00")),
    ]

    async def fake_get(db, project_id):
        return rows

    monkeypatch.setattr("app.harness.matchers.data.wbs_code_repo.get_by_project", fake_get)

    subs = await wbs_subcategories(db=None, project_id="p")
    assert subs == [
        Subcat(id=str(orphan_id), code="XX-01", description="", parent_code="",
               contract_sum=None),
        Subcat(id=str(uuid.UUID(int=2)), code="DM-01", description="Soft strip",
               parent_code="DM", contract_sum=12345.0),
    ]


@pytest.mark.asyncio
async def test_vps_records_maps_variations_and_provisional_sums(monkeypatch):
    v_id, ps_id = uuid.uuid4(), uuid.uuid4()
    variations = [SimpleNamespace(id=v_id, description="Extra footing",
                                  contractor_submission=Decimal("1500.50"))]
    sums = [SimpleNamespace(id=ps_id, description="Landscaping PS",
                            contract_sum=Decimal("20000.00"))]

    async def fake_vars(db, project_id):
        return variations

    async def fake_ps(db, project_id):
        return sums

    monkeypatch.setattr("app.harness.matchers.data.variation_repo.get_by_project", fake_vars)
    monkeypatch.setattr("app.harness.matchers.data.provisional_sum_repo.get_by_project", fake_ps)

    recs = await vps_records(db=None, project_id="p")
    assert recs == [
        VpsRecord(id=str(v_id), description="Extra footing", value=1500.5,
                  item_type="variation"),
        VpsRecord(id=str(ps_id), description="Landscaping PS", value=20000.0,
                  item_type="provisional_sum"),
    ]
