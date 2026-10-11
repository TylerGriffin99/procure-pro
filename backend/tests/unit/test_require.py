import pytest

from app.exceptions import NotFoundError, require


def test_require_none_raises_not_found_with_uniform_detail():
    with pytest.raises(NotFoundError) as excinfo:
        require(None, "Claim")
    assert excinfo.value.detail == "Claim not found"
    assert excinfo.value.status_code == 404


def test_require_returns_the_value_itself():
    value = object()
    assert require(value, "Thing") is value


def test_require_treats_empty_values_as_present():
    empty: list[int] = []
    assert require(empty, "x") is empty
    assert require(0, "x") == 0
