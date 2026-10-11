import calendar
from datetime import date, datetime, timedelta

from app.constants.values import DMY_DATE_PARTS, TWO_DIGIT_YEAR_CEILING, TWO_DIGIT_YEAR_CENTURY, WORKING_DAYS_OFFSET
from app.schemas.base import StrictModel


class DateParse(StrictModel):
    value: date | None
    warning: str | None = None  # set when a present date was unreadable; value is then None


def parse_ddmmyy(raw: str | None) -> DateParse:
    if not raw:
        return DateParse(value=None)
    unreadable = DateParse(value=None, warning=f"unparseable date {raw!r}")
    parts = raw.split("/")
    if len(parts) != DMY_DATE_PARTS:
        return unreadable
    try:
        day, month, year = (int(part) for part in parts)
        if year < TWO_DIGIT_YEAR_CEILING:
            year += TWO_DIGIT_YEAR_CENTURY
        return DateParse(value=date(year, month, day))
    except ValueError:
        return unreadable


def add_working_days(start: date, days: int) -> date:
    # Mon-Fri only; public holidays are not excluded.
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < calendar.SATURDAY:
            added += 1
    return current


def payment_due_20th(reference: date) -> date:
    if reference.month == calendar.DECEMBER:
        return date(reference.year + 1, 1, 20)
    return reference.replace(month=reference.month + 1, day=20)


def auto_fill_dates(claim_received: date | None) -> dict[str, date | None]:
    if not claim_received:
        return {}
    provisional = add_working_days(claim_received, WORKING_DAYS_OFFSET)
    schedule = add_working_days(provisional, WORKING_DAYS_OFFSET)
    payment = payment_due_20th(schedule)
    return {"provisional_payment_schedule_due": provisional, "payment_schedule_due": schedule, "payment_due": payment}


def format_long_date(value: date | datetime | None) -> str:
    if not value:
        return ""
    day = value.date() if isinstance(value, datetime) else value
    return day.strftime("%-d %B %Y")
