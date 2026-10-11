"""Unit tests for format playbook context loader."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import BadRequestError
from app.harness.context_loaders import load_format_playbook


@pytest.mark.asyncio
async def test_loads_wbpro_playbook():
    """Should load wbpro.md when format_detection says wbpro."""
    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    db = AsyncMock()

    format_json = json.dumps({"format": "wbpro", "confidence": 0.95, "markers_found": []})

    with patch("app.harness.phase_context.harness_repo") as mock_repo:
        mock_repo.read_workspace_file = AsyncMock(return_value=format_json)
        result = await load_format_playbook(db, project_id, session_id)

    assert "playbook_content" in result
    assert "WBPRO" in result["playbook_content"]
    assert len(result["playbook_content"]) > 100


@pytest.mark.asyncio
async def test_loads_generic_playbook():
    """Should load generic.md when format_detection says generic."""
    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    db = AsyncMock()

    format_json = json.dumps({"format": "generic", "confidence": 0.5, "markers_found": []})

    with patch("app.harness.phase_context.harness_repo") as mock_repo:
        mock_repo.read_workspace_file = AsyncMock(return_value=format_json)
        result = await load_format_playbook(db, project_id, session_id)

    assert "playbook_content" in result
    assert len(result["playbook_content"]) > 50


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [None, ""])
async def test_missing_format_detection_is_fatal(raw):
    db = AsyncMock()

    with patch("app.harness.phase_context.harness_repo") as mock_repo:
        mock_repo.read_workspace_file = AsyncMock(return_value=raw)
        with pytest.raises(BadRequestError, match="format_detection.json missing"):
            await load_format_playbook(db, uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw",
    [
        "{not json",
        json.dumps({"format": "procore", "confidence": 0.8, "markers_found": []}),
        json.dumps({"format": "wbpro"}),
    ],
)
async def test_invalid_format_detection_is_fatal(raw):
    db = AsyncMock()

    with patch("app.harness.phase_context.harness_repo") as mock_repo:
        mock_repo.read_workspace_file = AsyncMock(return_value=raw)
        with pytest.raises(BadRequestError, match="format_detection.json is invalid"):
            await load_format_playbook(db, uuid.uuid4(), uuid.uuid4())


def _no_playbook(fmt: str) -> str:
    raise FileNotFoundError(f"playbooks/formats/{fmt}.md")


@pytest.mark.asyncio
async def test_missing_playbook_file_propagates(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr("app.harness.context_loaders.load_playbook", _no_playbook)
    format_json = json.dumps({"format": "generic", "confidence": 0.5, "markers_found": []})

    with patch("app.harness.phase_context.harness_repo") as mock_repo:
        mock_repo.read_workspace_file = AsyncMock(return_value=format_json)
        with pytest.raises(FileNotFoundError, match="generic.md"):
            await load_format_playbook(db, uuid.uuid4(), uuid.uuid4())
