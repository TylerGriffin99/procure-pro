"""Smoke tests for variation, provisional_sum, claim, and wbs repo methods."""
from app.repos import variation_repo, provisional_sum_repo, claim_repo, wbs_code_repo


def test_variation_repo_has_create():
    assert callable(variation_repo.create)


def test_variation_repo_has_update():
    assert callable(variation_repo.update)


def test_variation_repo_has_delete():
    assert callable(variation_repo.delete)


def test_variation_repo_has_get_by_id():
    assert callable(variation_repo.get_by_id)


def test_variation_repo_has_delete_by_project():
    assert callable(variation_repo.delete_by_project)


def test_variation_repo_has_get_max_ci_number():
    assert callable(variation_repo.get_max_ci_number)


def test_ps_repo_has_create():
    assert callable(provisional_sum_repo.create)


def test_ps_repo_has_update():
    assert callable(provisional_sum_repo.update)


def test_ps_repo_has_delete():
    assert callable(provisional_sum_repo.delete)


def test_ps_repo_has_get_by_id():
    assert callable(provisional_sum_repo.get_by_id)


def test_ps_repo_has_delete_by_project():
    assert callable(provisional_sum_repo.delete_by_project)


def test_ps_repo_has_get_max_ps_number():
    assert callable(provisional_sum_repo.get_max_ps_number)


def test_claim_repo_has_delete_by_project():
    assert callable(claim_repo.delete_by_project)


def test_wbs_repo_has_get_by_id_with_children():
    assert callable(wbs_code_repo.get_by_id_with_children)
