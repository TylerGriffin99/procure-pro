from decimal import Decimal, InvalidOperation

from app.constants.values import BLANK_CELL, CENTS
from app.schemas.base import StrictModel

ZERO = Decimal("0")


class MoneyParse(StrictModel):
    value: Decimal
    warning: str | None = None  # set when the input was malformed; value is then 0 (D6)


def parse_money(raw: str | int | float | Decimal | None, *, blank: str = BLANK_CELL) -> MoneyParse:
    if raw is None or (isinstance(raw, str) and raw.strip() in {"", blank}):
        return MoneyParse(value=ZERO)
    value = raw if isinstance(raw, Decimal) else _decimal_or_none(raw)
    if value is None or not value.is_finite():
        return MoneyParse(value=ZERO, warning=f"unparseable money value {raw!r}")
    return MoneyParse(value=value)


def _decimal_or_none(raw: str | int | float) -> Decimal | None:
    text = str(raw) if isinstance(raw, int | float) else raw.strip().replace("$", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        value = Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None
    return -value if negative else value


def format_money(value: Decimal) -> str:
    return str(value.quantize(CENTS))
