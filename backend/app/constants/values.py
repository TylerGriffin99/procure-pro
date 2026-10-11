from decimal import Decimal
from typing import Final

from app.constants.enums import Country

CENTS: Final = Decimal("0.01")

# WBPro rows: variation rows carry an extra client_ref column the standard rows lack.
VARIATION_COLUMNS: Final = 9
STANDARD_COLUMNS: Final = 8

BLANK_CELL: Final = "-"

# Claim dates are DD/MM/YYYY; a two-digit year is read as 20YY.
DMY_DATE_PARTS: Final = 3
TWO_DIGIT_YEAR_CEILING: Final = 100
TWO_DIGIT_YEAR_CENTURY: Final = 2000

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
