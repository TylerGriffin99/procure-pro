from decimal import Decimal, InvalidOperation

from app.constants.values import BLANK_CELL, CENTS
from app.schemas.base import StrictModel

ZERO = Decimal("0")


class MoneyParse(StrictModel):
    value: Decimal
    warning: str | None = None  # set when the input was malformed; value is then 0 (D6)


def parse_money(raw: str | int | float | Decimal | None, *, blank: str = BLANK_CELL) -> MoneyParse:
    """Accepts commas, a leading "$", spaces and "(1.00)" negatives; never raises on bad text."""
    if raw is None:
        return MoneyParse(value=ZERO)
    if isinstance(raw, Decimal):
        return MoneyParse(value=raw)
    if isinstance(raw, int | float):
        text = str(raw)
    else:
        text = raw.strip()
        if not text or text == blank:
            return MoneyParse(value=ZERO)
        text = text.replace("$", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        value = Decimal(text.replace(",", ""))
    except InvalidOperation:
        return MoneyParse(value=ZERO, warning=f"unparseable money value {raw!r}")
    if not value.is_finite():
        return MoneyParse(value=ZERO, warning=f"unparseable money value {raw!r}")
    return MoneyParse(value=-value if negative else value)


def format_money(value: Decimal) -> str:
    return str(value.quantize(CENTS))
