"""Pure organizational domain values and invariants; no database or framework."""

from decimal import Decimal, InvalidOperation


def credits(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid credit amount") from exc
    if not amount.is_finite() or amount <= 0 or amount > 1_000_000_000:
        raise ValueError("Credit amount out of range")
    if amount.as_tuple().exponent < -4:
        raise ValueError("At most four decimal places supported")
    return amount
