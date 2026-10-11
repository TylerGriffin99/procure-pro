import pytest

from app.constants import CURRENCY_BY_COUNTRY


@pytest.mark.parametrize("country,expected_currency", [("NZ", "NZD"), ("AU", "AUD")])
def test_country_currency_mapping(country: str, expected_currency: str):
    assert CURRENCY_BY_COUNTRY[country] == expected_currency


def test_country_currency_mapping_completeness():
    """Every supported country must have a currency entry."""
    assert len(CURRENCY_BY_COUNTRY) == 2
    assert set(CURRENCY_BY_COUNTRY.keys()) == {"NZ", "AU"}
