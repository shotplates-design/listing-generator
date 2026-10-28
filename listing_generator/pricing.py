"""Asking prices from a target or a cost-basis markup. Photos never set a price."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from listing_generator.fees import FeeSchedule
from listing_generator.models import ClothingItem
from listing_generator.money import Money
from listing_generator.text import Conditions


@dataclass(frozen=True)
class PriceSuggestion:
    list_price: Decimal | None
    source: str
    summary: str


class PriceAdvisor:
    """Picks one asking price to draft on every platform."""

    @staticmethod
    def suggest(item: ClothingItem, config: dict | None = None) -> PriceSuggestion:
        schedule = config or FeeSchedule.load()
        condition = Conditions.label(item.condition)
        if item.target_price is not None and item.target_price > 0:
            if condition:
                summary = (
                    f"Condition is {condition}. Your target asking price is {Money.format(item.target_price)}, "
                    f"so every platform is drafted at {Money.format(item.target_price)}. "
                    "The condition did not change a price you set."
                )
            else:
                summary = (
                    f"Condition was not set. Your target asking price is {Money.format(item.target_price)}, "
                    f"so every platform is drafted at {Money.format(item.target_price)}. "
                    "No condition discount was applied."
                )
            return PriceSuggestion(item.target_price, "target", summary)
        if item.cost_basis is not None and item.cost_basis > 0 and item.condition:
            markup = Decimal(schedule["cost_basis_markup"][item.condition])
            raw = item.cost_basis * markup
            price = Money.nearest_dollar(raw)
            summary = (
                f"No target price was entered. Suggested ask is {Money.format(price)}, from a cost basis of "
                f"{Money.format(item.cost_basis)} × {markup} for {condition} condition, rounded to the nearest dollar. "
                "This is a markup heuristic, not a sold comp, and it is not read from the photos."
            )
            return PriceSuggestion(price, "cost_basis", summary)
        if item.cost_basis is not None and item.cost_basis > 0:
            summary = (
                f"No target price was entered. Cost basis is {Money.format(item.cost_basis)}, "
                "but condition is blank, so no markup was applied and no price was suggested."
            )
            return PriceSuggestion(None, "none", summary)
        summary = (
            "No target price was entered. A price was not estimated from the photos, "
            "and there is no cost basis with a confirmed condition to mark up."
        )
        return PriceSuggestion(None, "none", summary)
