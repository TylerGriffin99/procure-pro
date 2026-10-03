"""Smoke tests for assessment sub-item repo function signatures."""
from app.repos import assessment_line_item_repo, assessment_variation_repo, assessment_provisional_sum_repo


def test_line_item_repo_has_create():
    assert callable(assessment_line_item_repo.create)


def test_line_item_repo_has_update():
    assert callable(assessment_line_item_repo.update)


def test_line_item_repo_has_delete():
    assert callable(assessment_line_item_repo.delete)


def test_variation_repo_has_create():
    assert callable(assessment_variation_repo.create)


def test_variation_repo_has_update():
    assert callable(assessment_variation_repo.update)


def test_variation_repo_has_delete():
    assert callable(assessment_variation_repo.delete)


def test_ps_repo_has_create():
    assert callable(assessment_provisional_sum_repo.create)


def test_ps_repo_has_update():
    assert callable(assessment_provisional_sum_repo.update)


def test_ps_repo_has_delete():
    assert callable(assessment_provisional_sum_repo.delete)
