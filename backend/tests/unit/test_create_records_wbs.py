import uuid
from types import SimpleNamespace

import pytest

from app.constants.enums import WBSLevel
from app.harness.executors.create_records import wbs as wbs_module
from app.harness.schemas import WbsMatch

PARENT_ID = uuid.uuid4()
EXISTING_ID = uuid.uuid4()


@pytest.fixture
def created(monkeypatch):
    rows = [
        SimpleNamespace(id=PARENT_ID, code="EX", level=WBSLevel.category),
        SimpleNamespace(id=EXISTING_ID, code="EX-01", level=WBSLevel.subcategory),
    ]
    calls = []

    async def get_by_project(db, project_id):
        return rows

    async def create(db, **fields):
        calls.append(fields)
        return SimpleNamespace(id=uuid.uuid4(), **fields)

    monkeypatch.setattr(wbs_module.wbs_code_repo, "get_by_project", get_by_project)
    monkeypatch.setattr(wbs_module.wbs_code_repo, "create", create)
    return calls


async def resolve(matches):
    return await wbs_module.resolve_wbs(None, project_id=uuid.uuid4(), user_id=uuid.uuid4(), matches=matches)


async def test_existing_code_is_reused_even_when_marked_new(created):
    resolved = await resolve([WbsMatch(item_index=0, wbs_code="EX-01", is_new=True, confidence=0.9)])
    assert resolved == {0: EXISTING_ID}
    assert created == []


async def test_new_code_is_created_once_and_shared(created):
    resolved = await resolve(
        [
            WbsMatch(item_index=0, wbs_code="EX-02", parent_code="EX", is_new=True, confidence=0.9),
            WbsMatch(item_index=1, wbs_code="EX-02", parent_code="EX", is_new=True, confidence=0.9),
        ]
    )
    assert len(created) == 1 and created[0]["parent_id"] == PARENT_ID
    assert resolved[0] == resolved[1]


async def test_unknown_code_not_marked_new_is_left_uncategorised(created):
    assert await resolve([WbsMatch(item_index=0, wbs_code="ZZ-99", confidence=0.9)]) == {}


async def test_unresolvable_parent_logs_warning(created, caplog):
    with caplog.at_level("WARNING", logger=wbs_module.__name__):
        resolved = await resolve([WbsMatch(item_index=0, wbs_code="NEW-01", is_new=True, confidence=0.9)])
    assert resolved == {}
    assert any("unresolvable parent_code" in r.getMessage() and "NEW-01" in r.getMessage() for r in caplog.records)
