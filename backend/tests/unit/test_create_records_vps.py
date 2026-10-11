import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.harness.executors.create_records import vps as vps_module
from app.harness.schemas import ParsedClaimItem, VpsMatch
from app.models.provisional_sum import ProvisionalSum
from app.models.variation import Variation

VAR_A, VAR_B, PS_A = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


@pytest.fixture
def repos(monkeypatch):
    state = {
        "variations": [
            Variation(id=VAR_A, ci_number=1, description="Var A", contractor_submission=Decimal("100")),
            Variation(id=VAR_B, ci_number=2, description="Var B", contractor_submission=Decimal("200")),
        ],
        "sums": [ProvisionalSum(id=PS_A, ps_number=4, description="Landscaping", contract_sum=Decimal("50"))],
        "created": [],
        "updated": [],
    }

    async def get_variations(db, project_id):
        return list(state["variations"])

    async def get_sums(db, project_id):
        return list(state["sums"])

    async def max_ci(db, project_id):
        return max(v.ci_number for v in state["variations"])

    async def max_ps(db, project_id):
        return max(p.ps_number for p in state["sums"])

    async def create_variation(db, **fields):
        row = Variation(id=uuid.uuid4(), **fields)
        state["variations"].append(row)
        state["created"].append(row)
        return row

    async def create_ps(db, **fields):
        row = ProvisionalSum(id=uuid.uuid4(), **fields)
        state["sums"].append(row)
        state["created"].append(row)
        return row

    async def update(db, master, **fields):
        state["updated"].append((master.id, fields))
        return master

    for name, fn in [("get_by_project", get_variations), ("get_max_ci_number", max_ci), ("create", create_variation)]:
        monkeypatch.setattr(vps_module.variation_repo, name, fn)
    for name, fn in [("get_by_project", get_sums), ("get_max_ps_number", max_ps), ("create", create_ps)]:
        monkeypatch.setattr(vps_module.provisional_sum_repo, name, fn)
    monkeypatch.setattr(vps_module.variation_repo, "update", update)
    monkeypatch.setattr(vps_module.provisional_sum_repo, "update", update)
    return SimpleNamespace(**state)


def item(index, item_type, description, value="0"):
    return ParsedClaimItem(item_index=index, item_type=item_type, description=description, contract_value=value)


async def test_resolve_vps_links_matched_fallback_and_new_records(repos, caplog):
    items = [
        item(0, "variation", "Var A", "150"),
        item(1, "variation", "Bogus", "10"),
        item(2, "variation", "(U) var b"),
        item(3, "provisional_sum", "New PS", "75"),
    ]
    matches = [
        VpsMatch(item_index=0, item_type="variation", matched_id=str(VAR_A), confidence=0.9),
        VpsMatch(item_index=1, item_type="variation", matched_id=str(uuid.uuid4()), confidence=0.9),
    ]
    with caplog.at_level("INFO", logger=vps_module.__name__):
        links = await vps_module.resolve_vps(
            None, project_id=uuid.uuid4(), user_id=uuid.uuid4(), items=items, matches=matches
        )

    assert links.variations[0] == VAR_A
    assert repos.updated == [(VAR_A, {"contractor_submission": Decimal("150")})]
    [new_var, new_ps] = repos.created
    assert links.variations[1] == new_var.id and new_var.ci_number == 3
    assert links.variations[2] == VAR_B  # fallback matched by description, (U) prefix stripped
    assert links.provisional_sums == {3: new_ps.id} and new_ps.ps_number == 5
    assert "not found in existing variations, treating as unmatched" in caplog.text
    assert "Fallback matched variation item_index=2" in caplog.text


async def test_unapproved_prefix_is_stripped_from_new_variation(repos):
    links = await vps_module.resolve_vps(
        None,
        project_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        items=[item(0, "variation", "(U) Extra footing", "9")],
        matches=[VpsMatch(item_index=0, item_type="variation", confidence=0.5)],
    )
    [created] = repos.created
    assert links.variations == {0: created.id}
    assert (created.description, created.contractor_submission) == ("Extra footing", Decimal("9"))
