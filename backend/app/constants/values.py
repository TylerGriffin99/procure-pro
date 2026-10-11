from decimal import Decimal
from typing import Final

from app.constants.enums import Country, LlmProvider

CENTS: Final = Decimal("0.01")

# WBPro rows: variation rows carry an extra client_ref column the standard rows lack.
VARIATION_COLUMNS: Final = 9
STANDARD_COLUMNS: Final = 8

BLANK_CELL: Final = "-"

# Claim dates are DD/MM/YYYY; a two-digit year is read as 20YY.
DMY_DATE_PARTS: Final = 3
TWO_DIGIT_YEAR_CEILING: Final = 100
TWO_DIGIT_YEAR_CENTURY: Final = 2000

# Payment-schedule dates sit this many working days after the previous milestone.
WORKING_DAYS_OFFSET: Final = 5

COMMENT_PREFIX_INTERIM: Final = "Interim"
COMMENT_PREFIX_CLOSED_OUT: Final = "Closed Out"
COMMENT_SEPARATOR: Final = " - "
# Longest first: a separated prefix must be stripped whole before its bare form can match.
EXPORT_STRIPPED_COMMENT_PREFIXES: Final = (
    COMMENT_PREFIX_CLOSED_OUT + COMMENT_SEPARATOR,
    COMMENT_PREFIX_INTERIM + COMMENT_SEPARATOR,
    COMMENT_PREFIX_CLOSED_OUT,
    COMMENT_PREFIX_INTERIM,
)

PDF_MEDIA_TYPE: Final = "application/pdf"
XLSX_MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

CURRENCY_BY_COUNTRY: Final[dict[Country, str]] = {Country.NZ: "NZD", Country.AU: "AUD"}

# (base_url, or None for the OpenAI SDK default; name of the settings field holding the API key)
PROVIDER_TABLE: Final[dict[LlmProvider, tuple[str | None, str]]] = {
    LlmProvider.anthropic: ("https://api.anthropic.com/v1/", "anthropic_api_key"),
    LlmProvider.openai: (None, "openai_api_key"),
    LlmProvider.openrouter: ("https://openrouter.ai/api/v1", "open_router_api_key"),
    LlmProvider.deepseek: ("https://api.deepseek.com", "deepseek_api_key"),
}
