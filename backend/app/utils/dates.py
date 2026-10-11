import calendar
from datetime import date, timedelta

from app.constants.values import DMY_DATE_PARTS, TWO_DIGIT_YEAR_CEILING, TWO_DIGIT_YEAR_CENTURY, WORKING_DAYS_OFFSET


def parse_ddmmyy(raw: str | None) -> date | None:
    if not raw:
        return None
    parts = raw.split("/")
    if len(parts) != DMY_DATE_PARTS:
        return None
    try:
        day, month, year = (int(part) for part in parts)
        if year < TWO_DIGIT_YEAR_CEILING:
            year += TWO_DIGIT_YEAR_CENTURY
        return date(year, month, day)
    except ValueError:
        return None


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
