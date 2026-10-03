"""Unit tests for section_title–aware LLM categorisation."""
import json
from unittest.mock import MagicMock

import pytest


def _make_llm_response(results: list[dict]) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = json.dumps(results)
    return response


def _make_mock_client(results: list[dict], captured: list[str] | None = None):
    async def fake_create(**kwargs):
        if captured is not None:
            captured.append(kwargs["messages"][0]["content"])
        return _make_llm_response(results)

    client = MagicMock()
    client.chat.completions.create = fake_create
    return client


@pytest.mark.asyncio
async def test_section_title_included_in_prompt(monkeypatch):
    """Prompt sent to LLM must include [section: X] for each item."""
    from app.utils.categoriser import categorise_claim_items

    captured: list[str] = []
    llm_results = [
        {"ref_code": "1", "wbs_code": "PG-01", "wbs_description": "Netting",
         "parent_code": "PG", "is_new": True, "is_variation": True},
        {"ref_code": "4065", "wbs_code": "PG-02", "wbs_description": "Scaffolding",
         "parent_code": "PG", "is_new": True, "is_variation": False},
    ]
    mock_settings = MagicMock()
    mock_settings.open_router_api_key = "test-key"
    mock_settings.categoriser_model = "test-model"
    monkeypatch.setattr("app.utils.categoriser.settings", mock_settings)
    monkeypatch.setattr(
        "app.utils.categoriser.openai.AsyncOpenAI",
        lambda **kwargs: _make_mock_client(llm_results, captured),
    )

    items = [
        {"ref_code": "1", "description": "(U) Birdnetting in ambient area", "section_title": "Variation Works"},
        {"ref_code": "4065", "description": "Scaffolding and Encapsulation", "section_title": "Contract Works"},
    ]
    categories = [{"code": "PG", "description": "Preliminaries & General"}]

    await categorise_claim_items(items, categories, [])

    assert len(captured) == 1
    prompt = captured[0]
    assert "[section: Variation Works]" in prompt
    assert "[section: Contract Works]" in prompt


@pytest.mark.asyncio
async def test_items_without_section_title_still_work(monkeypatch):
    """Items with empty section_title should not error."""
    from app.utils.categoriser import categorise_claim_items

    llm_results = [
        {"ref_code": "4065", "wbs_code": "PG-01", "wbs_description": "Scaffolding",
         "parent_code": "PG", "is_new": True, "is_variation": False},
    ]
    mock_settings = MagicMock()
    mock_settings.open_router_api_key = "test-key"
    mock_settings.categoriser_model = "test-model"
    monkeypatch.setattr("app.utils.categoriser.settings", mock_settings)
    monkeypatch.setattr(
        "app.utils.categoriser.openai.AsyncOpenAI",
        lambda **kwargs: _make_mock_client(llm_results),
    )

    items = [
        {"ref_code": "4065", "description": "Scaffolding and Encapsulation", "section_title": ""},
    ]
    categories = [{"code": "PG", "description": "Preliminaries & General"}]

    results = await categorise_claim_items(items, categories, [])
    assert len(results) == 1


@pytest.mark.asyncio
async def test_variation_works_section_produces_is_variation_true(monkeypatch):
    """WBSMatch.is_variation must be True for items the LLM marks as variations."""
    from app.utils.categoriser import categorise_claim_items

    llm_results = [
        {"ref_code": "1", "wbs_code": "PG-01", "wbs_description": "Birdnetting",
         "parent_code": "PG", "is_new": True, "is_variation": True},
        {"ref_code": "4065", "wbs_code": "PG-02", "wbs_description": "Scaffolding",
         "parent_code": "PG", "is_new": True, "is_variation": False},
    ]
    mock_settings = MagicMock()
    mock_settings.open_router_api_key = "test-key"
    mock_settings.categoriser_model = "test-model"
    monkeypatch.setattr("app.utils.categoriser.settings", mock_settings)
    monkeypatch.setattr(
        "app.utils.categoriser.openai.AsyncOpenAI",
        lambda **kwargs: _make_mock_client(llm_results),
    )

    items = [
        {"ref_code": "1", "description": "(U) Birdnetting in ambient area", "section_title": "Variation Works"},
        {"ref_code": "4065", "description": "Scaffolding and Encapsulation", "section_title": "Contract Works"},
    ]
    categories = [{"code": "PG", "description": "Preliminaries & General"}]

    results = await categorise_claim_items(items, categories, [])
    by_ref = {m.ref_code: m for m in results}

    assert by_ref["1"].is_variation is True
    assert by_ref["4065"].is_variation is False
