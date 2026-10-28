"""Turns a confirmed clothing item into five platform drafts. No network calls."""

from __future__ import annotations

from decimal import Decimal

from listing_generator.categories import CategorySuggester
from listing_generator.descriptions import DescriptionBuilder
from listing_generator.fees import FeeCalculator, FeeSchedule
from listing_generator.models import ClothingItem, FacebookFulfillment, FeeBreakdown, PlatformListing, Platforms
from listing_generator.money import Money
from listing_generator.pricing import PriceAdvisor, PriceSuggestion
from listing_generator.tags import ItemSpecifics, TagBuilder
from listing_generator.text import Conditions, Departments, Text
from listing_generator.titles import TitleBuilder


class ListingGenerator:
    """Rule-based drafts. The same item always produces the same copy."""

    @staticmethod
    def prepare(item: ClothingItem) -> ClothingItem:
        return ListingGenerator._prepare(item)

    @staticmethod
    def generate(item: ClothingItem, config: dict | None = None) -> tuple[PlatformListing, ...]:
        schedule = config or FeeSchedule.load()
        prepared = ListingGenerator._prepare(item)
        suggestion = PriceAdvisor.suggest(prepared, schedule)
        categories = CategorySuggester.suggest(prepared)
        shipping = prepared.buyer_paid_shipping or Decimal("0")
        tax = prepared.sales_tax or Decimal("0")
        drafts: list[PlatformListing] = []
        fees: dict[str, FeeBreakdown | None] = {}
        for platform in Platforms.ORDER:
            fee = None
            if suggestion.list_price is not None:
                fee = FeeCalculator.calculate(
                    platform,
                    suggestion.list_price,
                    buyer_shipping=shipping,
                    sales_tax=tax,
                    item_type=prepared.item_type,
                    config=schedule,
                    facebook_fulfillment=prepared.facebook_fulfillment,
                )
            fees[platform] = fee
        best_net, leaders = ListingGenerator._leaders(fees)
        for platform in Platforms.ORDER:
            fee = fees[platform]
            display = schedule["platforms"][platform]["display_name"]
            specifics: tuple[tuple[str, str], ...] = ()
            missing: tuple[str, ...] = ()
            if platform == "ebay":
                specifics, missing = ItemSpecifics.ebay(prepared)
                tags: tuple[str, ...] = ()
                tags_label = "Item specifics"
            elif platform == "poshmark":
                tags = TagBuilder.poshmark(prepared, schedule)
                tags_label = "Style tags"
            elif platform == "depop":
                tags = TagBuilder.depop(prepared, schedule)
                tags_label = "Hashtags"
            elif platform == "mercari":
                tags = TagBuilder.mercari(prepared, schedule)
                tags_label = "Keywords"
            elif platform == "whatnot":
                tags = TagBuilder.whatnot(prepared)
                tags_label = "Attributes"
            elif platform == "facebook_marketplace":
                specifics, missing = ItemSpecifics.facebook(prepared)
                tags = ()
                tags_label = "Tags"
            else:
                raise KeyError(platform)
            equalized, equalized_note = ListingGenerator._equalized(
                platform,
                display,
                suggestion,
                fee,
                best_net,
                leaders,
                prepared,
                shipping,
                tax,
                schedule,
            )
            drafts.append(
                PlatformListing(
                    platform=platform,
                    display_name=display,
                    title=TitleBuilder.for_platform(platform, prepared, schedule),
                    title_limit=TitleBuilder.limit(platform, schedule),
                    description=DescriptionBuilder.build(prepared, platform, schedule),
                    description_limit=DescriptionBuilder.limit(platform, schedule),
                    category=categories[platform].path,
                    category_note=categories[platform].note,
                    tags_label=tags_label,
                    tags=tags,
                    item_specifics=specifics,
                    missing_specifics=missing,
                    list_price=suggestion.list_price,
                    price_rationale=ListingGenerator._rationale(prepared, suggestion, fee, display, platform),
                    fee=fee,
                    equalized_list_price=equalized,
                    equalized_note=equalized_note,
                    checklist=ListingGenerator._checklist(prepared, suggestion),
                    polish="off",
                )
            )
        from listing_generator.polish import ListingPolish
        from listing_generator.rules import PlatformRules

        checked = tuple(PlatformRules.enforce(listing) for listing in drafts)
        return ListingPolish.apply(checked)

    @staticmethod
    def _prepare(item: ClothingItem) -> ClothingItem:
        known_conditions = {key for key, _label in Conditions.CHOICES if key}
        known_departments = {key for key, _label in Departments.CHOICES if key}
        condition = item.condition
        if condition and condition not in known_conditions:
            condition = Conditions.normalize(condition) or ""
        department = item.gender_department
        if department and department not in known_departments:
            department = Departments.normalize(department) or ""
        measurements = {
            key: Text.squash(value)
            for key, value in item.measurements.items()
            if Text.squash(value)
        }
        return ClothingItem(
            brand=item.brand.strip(),
            item_type=item.item_type.strip(),
            size_tagged=item.size_tagged.strip(),
            color=item.color.strip(),
            material=item.material.strip(),
            origin=item.origin.strip(),
            condition=condition,
            flaws=item.flaws.strip(),
            style_era=item.style_era.strip(),
            gender_department=department,
            measurements=measurements,
            cost_basis=item.cost_basis,
            target_price=item.target_price,
            buyer_paid_shipping=item.buyer_paid_shipping,
            sales_tax=item.sales_tax,
            facebook_fulfillment=FacebookFulfillment.normalize(item.facebook_fulfillment),
            field_flags=dict(item.field_flags),
            field_confidence=dict(item.field_confidence),
            review_notes=list(item.review_notes),
        )

    @staticmethod
    def _rationale(
        item: ClothingItem,
        suggestion: PriceSuggestion,
        fee: FeeBreakdown | None,
        display: str,
        platform: str,
    ) -> str:
        parts = [suggestion.summary]
        if platform == "facebook_marketplace" and fee is not None:
            if item.facebook_fulfillment == "shipped":
                parts.append(
                    "This Facebook draft uses shipped checkout, so the config selling fee is applied. Verify that rate before posting."
                )
            else:
                parts.append(
                    "This Facebook draft uses local pickup, so the selling fee is $0.00. Verify the shipped rate in the fee config before you offer shipping."
                )
        if fee is not None:
            parts.append(
                f"{display}'s fee on {Money.format(fee.list_price)} is {Money.format(fee.total_fee)}, "
                f"so the net is {Money.format(fee.net)}."
            )
            if item.cost_basis is not None and item.cost_basis > 0:
                if fee.net < item.cost_basis:
                    parts.append(
                        f"That net is below your cost basis of {Money.format(item.cost_basis)}."
                    )
                else:
                    parts.append(
                        f"That net covers your cost basis of {Money.format(item.cost_basis)}."
                    )
        return " ".join(parts)

    @staticmethod
    def _leaders(
        fees: dict[str, FeeBreakdown | None],
    ) -> tuple[Decimal | None, tuple[str, ...]]:
        priced = [fee for fee in fees.values() if fee is not None]
        if not priced:
            return None, ()
        best = max(fee.net for fee in priced)
        names = tuple(fee.platform for fee in priced if fee.net == best)
        return best, names

    @staticmethod
    def _equalized(
        platform: str,
        display: str,
        suggestion: PriceSuggestion,
        fee: FeeBreakdown | None,
        best_net: Decimal | None,
        leaders: tuple[str, ...],
        item: ClothingItem,
        shipping: Decimal,
        tax: Decimal,
        config: dict,
    ) -> tuple[Decimal | None, str]:
        if fee is None or best_net is None or suggestion.list_price is None:
            return None, ""
        if platform in leaders:
            return suggestion.list_price, "At this asking price, this platform ties for the highest net."
        match = FeeCalculator.price_for_net(
            platform,
            best_net,
            buyer_shipping=shipping,
            sales_tax=tax,
            item_type=item.item_type,
            config=config,
            facebook_fulfillment=item.facebook_fulfillment,
        )
        leader_names = ", ".join(config["platforms"][name]["display_name"] for name in leaders)
        if match is None:
            return None, (
                f"These rates cannot reach a net of {Money.format(best_net)} on {display}. "
                f"That net is the high one at {Money.format(suggestion.list_price)}, on {leader_names}."
            )
        return match, (
            f"To net {Money.format(best_net)} (the high net at {Money.format(suggestion.list_price)}, "
            f"on {leader_names}), list here at {Money.format(match)}."
        )

    @staticmethod
    def _checklist(item: ClothingItem, suggestion: PriceSuggestion) -> tuple[str, ...]:
        lines = [
            "Copy the draft into the marketplace yourself. This app does not post listings.",
        ]
        if not any(item.measurements.values()):
            lines.append("Add measurements before posting. They were not estimated from the photos.")
        if not item.condition:
            lines.append("Set a condition before posting. None was confirmed.")
        if not item.flaws:
            lines.append("Look the item over and add any flaws. None were confirmed.")
        if suggestion.list_price is None:
            lines.append("Enter a target price, or a cost basis plus a condition, to calculate fees and net.")
        if item.field_flags:
            lines.append("Review the flagged fields on the details form before you copy this draft.")
        return tuple(lines)
