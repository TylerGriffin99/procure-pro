import json

import pytest

from app.exceptions import BadRequestError
from app.harness.matchers.data import read_parsed_items
from app.repos import harness_repo
from tests.integration.test_harness_llm_single import _make_session


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [None, "", json.dumps({"metadata": {}})])
async def test_read_items_missing_or_malformed_raises(client, db_session, raw):
    session = await _make_session(client, db_session)
    if raw is not None:
        await harness_repo.write_workspace_file(db_session, session.id, "parsed_claim.json", raw)
    with pytest.raises(BadRequestError, match="parsed_claim.json"):
        await read_parsed_items(db_session, session.id)
