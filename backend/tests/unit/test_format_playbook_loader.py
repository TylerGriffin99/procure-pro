"""Unit tests for format playbook context loader."""
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.harness.context_loaders import load_format_playbook


@pytest.mark.asyncio
async def test_loads_wbpro_playbook():
    """Should load wbpro.md when format_detection says wbpro."""
    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    db = AsyncMock()

    format_json = json.dumps({"format": "wbpro", "confidence": 0.95, "markers_found": []})

    with patch("app.harness.context_loaders.harness_repo") as mock_repo:
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

    with patch("app.harness.context_loaders.harness_repo") as mock_repo:
        mock_repo.read_workspace_file = AsyncMock(return_value=format_json)
        result = await load_format_playbook(db, project_id, session_id)

    assert "playbook_content" in result
    assert len(result["playbook_content"]) > 50


@pytest.mark.asyncio
async def test_missing_format_detection_returns_fallback():
    """Should return fallback text when format_detection.json not found."""
    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    db = AsyncMock()

    with patch("app.harness.context_loaders.harness_repo") as mock_repo:
        mock_repo.read_workspace_file = AsyncMock(return_value=None)
        result = await load_format_playbook(db, project_id, session_id)

    assert "playbook_content" in result
    assert "No format-specific playbook" in result["playbook_content"]


@pytest.mark.asyncio
async def test_unknown_format_returns_fallback():
    """Should return fallback text when format is not recognised."""
    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    db = AsyncMock()

    format_json = json.dumps({"format": "procore", "confidence": 0.8, "markers_found": []})

    with patch("app.harness.context_loaders.harness_repo") as mock_repo:
        mock_repo.read_workspace_file = AsyncMock(return_value=format_json)
        result = await load_format_playbook(db, project_id, session_id)

    assert "playbook_content" in result
    assert "No format-specific playbook" in result["playbook_content"]
