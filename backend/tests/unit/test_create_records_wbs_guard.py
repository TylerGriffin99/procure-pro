import json
import uuid

import pytest

from app.harness.executors import create_records as cr


class _Stop(Exception):
    pass


@pytest.mark.asyncio
async def test_unresolvable_parent_logs_warning(monkeypatch, caplog):
    parsed = {"metadata": {}, "summary": {}, "line_items": [
        {"item_index": 0, "item_type": "contract_work", "description": "x"}]}
    matches = [{"item_index": 0, "wbs_code": "NEW-01", "is_new": True, "parent_code": ""}]
    files = {"parsed_claim.json": json.dumps(parsed), "wbs_matches.json": json.dumps(matches)}

    async def read(db, sid, name):
        return files.get(name)

    async def project(db, pid):
        return object()

    async def no_wbs(db, pid):
        return []

    async def stop(db, pid):
        raise _Stop  # halt right after the WBS loop

    monkeypatch.setattr(cr.harness_repo, "read_workspace_file", read)
    monkeypatch.setattr(cr.project_repo, "get_by_id", project)
    monkeypatch.setattr(cr.wbs_code_repo, "get_by_project", no_wbs)
    monkeypatch.setattr(cr.variation_repo, "get_by_project", stop)

    with caplog.at_level("WARNING", logger=cr.__name__):
        with pytest.raises(_Stop):
            await cr.execute_create_records(None, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), {})
    assert any("unresolvable parent_code" in r.getMessage() and "NEW-01" in r.getMessage()
               for r in caplog.records)
