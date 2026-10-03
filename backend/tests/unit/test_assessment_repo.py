"""Smoke tests for assessment_repo function signatures."""
from inspect import signature
from app.repos import assessment_repo


def test_get_by_id_accepts_eager_loading_flags():
    sig = signature(assessment_repo.get_by_id)
    params = sig.parameters
    assert "with_line_items" in params
    assert "with_variations" in params
    assert "with_provisional_sums" in params
    assert params["with_line_items"].default is True
    assert params["with_variations"].default is True
    assert params["with_provisional_sums"].default is True


def test_get_latest_by_claim_accepts_eager_loading_flags():
    sig = signature(assessment_repo.get_latest_by_claim)
    params = sig.parameters
    assert "with_line_items" in params


def test_get_latest_finalised_accepts_eager_loading_flags():
    sig = signature(assessment_repo.get_latest_finalised)
    params = sig.parameters
    assert "with_line_items" in params


def test_add_function_exists():
    assert callable(assessment_repo.add)


def test_delete_by_project_function_exists():
    assert callable(assessment_repo.delete_by_project)


def test_revert_to_draft_function_exists():
    from app.services import assessment_service
    assert callable(assessment_service.revert_to_draft)


def test_revert_to_draft_signature():
    from inspect import signature
    from app.services import assessment_service
    sig = signature(assessment_service.revert_to_draft)
    params = list(sig.parameters.keys())
    assert params == ["db", "project_id", "assessment_id", "user"]
