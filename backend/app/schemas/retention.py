from decimal import Decimal

from app.schemas.base import StrictModel


class RetentionTier(StrictModel):
    percentage: Decimal
    up_to_amount: Decimal | None  # None: the tier covers the remainder
