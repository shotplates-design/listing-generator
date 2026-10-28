"""Dollar amounts as cents, rounded half up and away from zero on a tie."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class MoneyError(ValueError):
    """A price field was not a dollar amount."""


class Money:
    QUANT = Decimal("0.01")
    DOLLAR = Decimal("1")

    @staticmethod
    def quantize(value: Decimal) -> Decimal:
        return value.quantize(Money.QUANT, rounding=ROUND_HALF_UP)

    @staticmethod
    def nearest_dollar(value: Decimal) -> Decimal:
        return value.quantize(Money.DOLLAR, rounding=ROUND_HALF_UP)

    @staticmethod
    def parse(text: object) -> Decimal | None:
        """Parse a dollar amount. Blank becomes None. Zero is kept."""
        if text is None:
            return None
        if isinstance(text, Decimal):
            if not text.is_finite() or text < 0:
                raise MoneyError("Amounts cannot be negative.")
            return Money.quantize(text)
        if isinstance(text, bool) or isinstance(text, float):
            raise MoneyError("Enter a dollar amount as text so cents stay exact.")
        if isinstance(text, int):
            if text < 0:
                raise MoneyError("Amounts cannot be negative.")
            return Money.quantize(Decimal(text))
        cleaned = str(text).strip().replace("$", "").replace(",", "")
        if cleaned == "":
            return None
        try:
            value = Decimal(cleaned)
        except InvalidOperation as exc:
            raise MoneyError(f"Enter a dollar amount, not {text!r}.") from exc
        if not value.is_finite():
            raise MoneyError("Enter a dollar amount.")
        if value < 0:
            raise MoneyError("Amounts cannot be negative.")
        return Money.quantize(value)

    @staticmethod
    def format(value: Decimal) -> str:
        quantized = Money.quantize(value)
        sign = "-" if quantized < 0 else ""
        return f"{sign}${abs(quantized):,.2f}"

    @staticmethod
    def percent_label(rate: Decimal) -> str:
        percent = rate * Decimal("100")
        text = f"{percent:.4f}".rstrip("0").rstrip(".")
        return f"{text}%"

    @staticmethod
    def require_positive(value: Decimal | None, label: str) -> Decimal | None:
        if value is None:
            return None
        if value <= 0:
            raise MoneyError(f"{label} has to be above zero, or left blank.")
        return value
