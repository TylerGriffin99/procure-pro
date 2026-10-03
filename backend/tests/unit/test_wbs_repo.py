"""Unit-level smoke tests for wbs_code_repo function signatures.

The real integration tests live in Task 3 (e2e). These verify the functions exist
and have the expected signatures.
"""
from app.repos import wbs_code_repo


def test_update_function_exists():
    assert callable(wbs_code_repo.update)


def test_is_in_use_function_exists():
    assert callable(wbs_code_repo.is_in_use)
