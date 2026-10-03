import pytest

from app.schemas.user import COUNTRY_CURRENCY_MAP


@pytest.mark.parametrize("country,expected_currency", [
    ("NZ", "NZD"),
    ("AU", "AUD"),
])
def test_country_currency_mapping(country: str, expected_currency: str):
    assert COUNTRY_CURRENCY_MAP[country] == expected_currency


def test_country_currency_mapping_completeness():
    """Every supported country must have a currency entry."""
    assert len(COUNTRY_CURRENCY_MAP) == 2
    assert set(COUNTRY_CURRENCY_MAP.keys()) == {"NZ", "AU"}
