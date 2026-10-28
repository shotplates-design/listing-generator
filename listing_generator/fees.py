"""Fee math. Rates come from config/fees.yaml and nowhere else."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from listing_generator.models import FeeBreakdown, FeeLine
from listing_generator.money import Money


class FeeSchedule:
    """Loads the single fee config."""

    @staticmethod
    def path() -> Path:
        import os

        override = os.environ.get("LISTING_FEE_CONFIG")
        if override:
            return Path(override)
        return Path(__file__).resolve().parents[1] / "config" / "fees.yaml"

    @staticmethod
    @lru_cache(maxsize=4)
    def load(path: str | None = None) -> dict:
        config_path = Path(path) if path else FeeSchedule.path()
        with config_path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict) or "platforms" not in data:
            raise ValueError(f"Fee config at {config_path} is missing platforms.")
        return data

    @staticmethod
    def clear_cache() -> None:
        FeeSchedule.load.cache_clear()


@dataclass
class _Quote:
    list_price: Decimal
    fee_base: Decimal
    lines: tuple[FeeLine, ...]
    total_fee: Decimal
    net: Decimal
    formula: str
    notes: tuple[str, ...]
    profile: str


class FeeProfile:
    """Picks the eBay clothing row from the item type. Other platforms have one row."""

    @staticmethod
    def ebay(item_type: str, config: dict) -> str:
        text = item_type.lower()
        keywords = config["platforms"]["ebay"]["keywords"]
        for name in ("athletic_shoes", "handbags"):
            for phrase in keywords[name]:
                if phrase.lower() in text:
                    return name
        return "clothing"


class FeeCalculator:
    """Turns a list price into a fee, a net, and the arithmetic in words."""

    @staticmethod
    def calculate(
        platform: str,
        list_price: Decimal,
        *,
        buyer_shipping: Decimal = Decimal("0"),
        sales_tax: Decimal = Decimal("0"),
        item_type: str = "",
        config: dict | None = None,
        facebook_fulfillment: str = "local_pickup",
    ) -> FeeBreakdown:
        schedule = config or FeeSchedule.load()
        quote = FeeCalculator._quote(
            platform,
            Money.quantize(list_price),
            Money.quantize(buyer_shipping),
            Money.quantize(sales_tax),
            item_type,
            schedule,
            facebook_fulfillment,
        )
        return FeeBreakdown(
            platform=platform,
            list_price=quote.list_price,
            fee_base=quote.fee_base,
            lines=quote.lines,
            total_fee=quote.total_fee,
            net=quote.net,
            formula=quote.formula,
            notes=quote.notes,
        )

    @staticmethod
    def price_for_net(
        platform: str,
        desired_net: Decimal,
        *,
        buyer_shipping: Decimal = Decimal("0"),
        sales_tax: Decimal = Decimal("0"),
        item_type: str = "",
        config: dict | None = None,
        facebook_fulfillment: str = "local_pickup",
    ) -> Decimal | None:
        """Smallest list price, in cents, whose net is at least desired_net."""
        schedule = config or FeeSchedule.load()
        target = Money.quantize(desired_net)
        if target <= 0:
            return None
        shipping = Money.quantize(buyer_shipping)
        tax = Money.quantize(sales_tax)
        price = target
        limit = target * Decimal("3") + Decimal("30")
        while price <= limit:
            quote = FeeCalculator._quote(
                platform, price, shipping, tax, item_type, schedule, facebook_fulfillment
            )
            if quote.net >= target:
                return price
            price = Money.quantize(price + Decimal("0.01"))
        return None

    @staticmethod
    def _quote(
        platform: str,
        price: Decimal,
        shipping: Decimal,
        tax: Decimal,
        item_type: str,
        config: dict,
        fulfillment: str = "local_pickup",
    ) -> _Quote:
        if platform == "ebay":
            return FeeCalculator._ebay(price, shipping, tax, item_type, config)
        if platform == "poshmark":
            return FeeCalculator._poshmark(price, shipping, tax, config)
        if platform == "depop":
            return FeeCalculator._depop(price, shipping, tax, config)
        if platform == "mercari":
            return FeeCalculator._mercari(price, shipping, tax, config)
        if platform == "whatnot":
            return FeeCalculator._whatnot(price, shipping, tax, config)
        if platform == "facebook_marketplace":
            return FeeCalculator._facebook(price, shipping, tax, config, fulfillment)
        raise KeyError(platform)

    @staticmethod
    def _ebay(price: Decimal, shipping: Decimal, tax: Decimal, item_type: str, config: dict) -> _Quote:
        rates = config["platforms"]["ebay"]
        base = price + shipping + tax
        profile = FeeProfile.ebay(item_type, config)
        notes = [
            "US seller without a Store subscription. Top Rated and promoted-listing discounts are not applied.",
            "Insertion fees are not included.",
            "Net is the item price minus fees. Buyer-paid shipping is not treated as profit, and sales tax is not treated as profit.",
        ]
        lines: list[FeeLine] = []
        if profile == "athletic_shoes" and base >= Decimal(rates["athletic_shoes_threshold"]):
            percent = Decimal(rates["athletic_shoes_percent"])
            variable = Money.quantize(base * percent)
            lines.append(FeeLine(f"Final value fee {Money.percent_label(percent)} × {Money.format(base)}", variable))
            formula_fee = (
                f"Athletic shoes profile: fee base {Money.format(base)} is "
                f"{Money.format(Decimal(rates['athletic_shoes_threshold']))} or more, so the final value fee is "
                f"{Money.percent_label(percent)} × {Money.format(base)} = {Money.format(variable)} "
                f"and the per-order fee is not charged."
            )
            fixed = Decimal("0")
        elif profile == "handbags":
            threshold = Decimal(rates["handbag_threshold"])
            if base <= threshold:
                percent = Decimal(rates["handbag_percent"])
                band = f"{Money.format(threshold)} or less"
            else:
                percent = Decimal(rates["handbag_percent_above"])
                band = f"over {Money.format(threshold)}"
            variable = Money.quantize(base * percent)
            fixed = FeeCalculator._ebay_per_order(base, rates)
            lines.append(FeeLine(f"Final value fee {Money.percent_label(percent)} × {Money.format(base)}", variable))
            lines.append(FeeLine("Per-order fee", fixed))
            formula_fee = (
                f"Handbag profile: fee base {Money.format(base)} is {band}, so the final value fee is "
                f"{Money.percent_label(percent)} × {Money.format(base)} = {Money.format(variable)}. "
                f"{FeeCalculator._per_order_sentence(base, rates, fixed)}"
            )
        else:
            if profile == "athletic_shoes":
                notes.append(
                    "Athletic shoes under "
                    f"{Money.format(Decimal(rates['athletic_shoes_threshold']))} use the standard clothing rate."
                )
            threshold = Decimal(rates["clothing_threshold"])
            lower_rate = Decimal(rates["clothing_percent"])
            upper_rate = Decimal(rates["clothing_percent_above"])
            lower_base = base if base <= threshold else threshold
            upper_base = Decimal("0") if base <= threshold else base - threshold
            lower_fee = Money.quantize(lower_base * lower_rate)
            upper_fee = Money.quantize(upper_base * upper_rate)
            fixed = FeeCalculator._ebay_per_order(base, rates)
            lines.append(FeeLine(f"Final value fee {Money.percent_label(lower_rate)} × {Money.format(lower_base)}", lower_fee))
            if upper_fee > 0:
                lines.append(
                    FeeLine(
                        f"Final value fee {Money.percent_label(upper_rate)} × {Money.format(upper_base)} above {Money.format(threshold)}",
                        upper_fee,
                    )
                )
            lines.append(FeeLine("Per-order fee", fixed))
            variable = lower_fee + upper_fee
            if upper_fee > 0:
                slice_text = (
                    f"Final value fee {Money.percent_label(lower_rate)} × {Money.format(lower_base)} = {Money.format(lower_fee)}, "
                    f"plus {Money.percent_label(upper_rate)} × {Money.format(upper_base)} on the portion above {Money.format(threshold)} "
                    f"= {Money.format(upper_fee)}."
                )
            else:
                slice_text = (
                    f"Final value fee {Money.percent_label(lower_rate)} × {Money.format(base)} = {Money.format(lower_fee)}."
                )
            formula_fee = f"{FeeCalculator._base_sentence(price, shipping, tax)} {slice_text} {FeeCalculator._per_order_sentence(base, rates, fixed)}"
        if profile == "athletic_shoes" and base >= Decimal(rates["athletic_shoes_threshold"]):
            formula_fee = f"{FeeCalculator._base_sentence(price, shipping, tax)} {formula_fee}"
        if profile == "handbags":
            formula_fee = f"{FeeCalculator._base_sentence(price, shipping, tax)} {formula_fee}"
        total = Money.quantize(sum((line.amount for line in lines), Decimal("0")))
        net = Money.quantize(price - total)
        formula = (
            f"{formula_fee} Total fee {Money.format(total)}. "
            f"Net {Money.format(price)} − {Money.format(total)} = {Money.format(net)}."
        )
        notes.extend(FeeCalculator._shipping_tax_notes("eBay", shipping, tax, charges_shipping=True, charges_tax=True))
        return _Quote(price, base, tuple(lines), total, net, " ".join(formula.split()), tuple(notes), profile)

    @staticmethod
    def _ebay_per_order(base: Decimal, rates: dict) -> Decimal:
        threshold = Decimal(rates["per_order_threshold"])
        if base <= threshold:
            return Decimal(rates["per_order_up_to_10"])
        return Decimal(rates["per_order_above_10"])

    @staticmethod
    def _per_order_sentence(base: Decimal, rates: dict, fixed: Decimal) -> str:
        threshold = Decimal(rates["per_order_threshold"])
        if base <= threshold:
            relation = f"{Money.format(threshold)} or less"
        else:
            relation = f"over {Money.format(threshold)}"
        return f"Per-order fee {Money.format(fixed)} because the fee base is {relation}."

    @staticmethod
    def _poshmark(price: Decimal, shipping: Decimal, tax: Decimal, config: dict) -> _Quote:
        rates = config["platforms"]["poshmark"]
        cutoff = Decimal(rates["flat_below"])
        if price < cutoff:
            fee = Decimal(rates["flat_fee"])
            lines = (FeeLine(f"Flat fee for a sale under {Money.format(cutoff)}", fee),)
            reason = f"Flat fee {Money.format(fee)} because the sale is under {Money.format(cutoff)}."
        else:
            fee = Money.quantize(price * Decimal(rates["percent"]))
            lines = (FeeLine(f"Commission {Money.percent_label(Decimal(rates['percent']))} × {Money.format(price)}", fee),)
            reason = (
                f"Commission {Money.percent_label(Decimal(rates['percent']))} × {Money.format(price)} = {Money.format(fee)} "
                f"because the sale is {Money.format(cutoff)} or more."
            )
        net = Money.quantize(price - fee)
        formula = (
            f"Fee base {Money.format(price)} (item price; Poshmark does not charge commission on shipping). "
            f"{reason} Total fee {Money.format(fee)}. "
            f"Net {Money.format(price)} − {Money.format(fee)} = {Money.format(net)}."
        )
        notes = [
            "Poshmark's US commission covers the prepaid label on a normal domestic sale. A separate shipping line was not added.",
            "The Texas seller-fee tax is not included.",
        ]
        if shipping > 0 or tax > 0:
            notes.append("Buyer-paid shipping and sales tax entered on the form are ignored for Poshmark.")
        return _Quote(price, price, lines, fee, net, formula, tuple(notes), "standard")

    @staticmethod
    def _depop(price: Decimal, shipping: Decimal, tax: Decimal, config: dict) -> _Quote:
        rates = config["platforms"]["depop"]
        base = price + shipping + tax
        percent = Decimal(rates["processing_percent"])
        fixed = Decimal(rates["processing_fixed"])
        selling = Money.quantize(base * Decimal(rates["selling_percent"]))
        processing_percent_fee = Money.quantize(base * percent)
        processing = processing_percent_fee + fixed
        total = selling + processing
        net = Money.quantize(price - total)
        lines = (
            FeeLine("Selling fee", selling),
            FeeLine(f"Payment processing {Money.percent_label(percent)} × {Money.format(base)}", processing_percent_fee),
            FeeLine("Payment processing fixed fee", fixed),
        )
        formula = (
            f"{FeeCalculator._base_sentence(price, shipping, tax)} "
            f"Selling fee {Money.format(selling)}. "
            f"Payment processing {Money.percent_label(percent)} × {Money.format(base)} = {Money.format(processing_percent_fee)}, "
            f"plus {Money.format(fixed)}, totals {Money.format(processing)}. "
            f"Total fee {Money.format(total)}. "
            f"Net {Money.format(price)} − {Money.format(total)} = {Money.format(net)}."
        )
        notes = [
            "US Depop selling fee is $0. Depop Boost is not included.",
            "Net is the item price minus fees. Buyer-paid shipping is not treated as profit, and sales tax is not treated as profit.",
        ]
        notes.extend(FeeCalculator._shipping_tax_notes("Depop", shipping, tax, charges_shipping=True, charges_tax=True))
        return _Quote(price, base, lines, total, net, formula, tuple(notes), "us")

    @staticmethod
    def _mercari(price: Decimal, shipping: Decimal, tax: Decimal, config: dict) -> _Quote:
        rates = config["platforms"]["mercari"]
        base = price + shipping
        percent = Decimal(rates["percent"])
        fee = Money.quantize(base * percent)
        net = Money.quantize(price - fee)
        lines = (FeeLine(f"Selling fee {Money.percent_label(percent)} × {Money.format(base)}", fee),)
        formula = (
            f"Fee base {Money.format(base)} ({FeeCalculator._parts(price, shipping, Decimal('0'), include_tax=False)}). "
            f"Selling fee {Money.percent_label(percent)} × {Money.format(base)} = {Money.format(fee)}. "
            f"Total fee {Money.format(fee)}. "
            f"Net {Money.format(price)} − {Money.format(fee)} = {Money.format(net)}."
        )
        notes = [
            "Mercari charges this selling fee and no separate payment-processing fee.",
            "A label you buy yourself is not a Mercari fee and is not subtracted here.",
            "Sales tax is not part of Mercari's selling-fee base in this calculator.",
        ]
        if shipping == 0:
            notes.append(
                "Buyer-paid shipping was left at $0.00. Add it if the buyer pays a shipping amount Mercari includes in the 10% fee."
            )
        else:
            notes.append("Buyer-paid shipping is included in Mercari's fee base and is not added to the payout.")
        if tax > 0:
            notes.append("The sales-tax amount on the form is not included in the Mercari fee.")
        return _Quote(price, base, lines, fee, net, formula, tuple(notes), "standard")

    @staticmethod
    def _whatnot(price: Decimal, shipping: Decimal, tax: Decimal, config: dict) -> _Quote:
        rates = config["platforms"]["whatnot"]
        commission_rate = Decimal(rates["commission_percent"])
        processing_rate = Decimal(rates["processing_percent"])
        fixed = Decimal(rates["processing_fixed"])
        processing_base = price + shipping + tax
        commission = Money.quantize(price * commission_rate)
        processing_percent_fee = Money.quantize(processing_base * processing_rate)
        processing = processing_percent_fee + fixed
        total = commission + processing
        net = Money.quantize(price - total)
        lines = (
            FeeLine(f"Commission {Money.percent_label(commission_rate)} × {Money.format(price)}", commission),
            FeeLine(
                f"Payment processing {Money.percent_label(processing_rate)} × {Money.format(processing_base)}",
                processing_percent_fee,
            ),
            FeeLine("Payment processing fixed fee", fixed),
        )
        formula = (
            f"Commission {Money.percent_label(commission_rate)} × {Money.format(price)} item = {Money.format(commission)} "
            f"(shipping and tax are excluded). "
            f"Payment processing {Money.percent_label(processing_rate)} × {Money.format(processing_base)} = {Money.format(processing_percent_fee)}, "
            f"plus {Money.format(fixed)}, totals {Money.format(processing)}. "
            f"Processing base is {FeeCalculator._parts(price, shipping, tax, include_tax=True)}. "
            f"Total fee {Money.format(total)}. "
            f"Net {Money.format(price)} − {Money.format(total)} = {Money.format(net)}."
        )
        notes = [
            "Default Whatnot commission is 8% of the item price. Some categories and higher-volume sellers pay less, down to about 3%. Change commission_percent in the fee config if that applies.",
            "Net is the item price minus fees. Buyer-paid shipping is not treated as profit, and sales tax is not treated as profit.",
        ]
        if shipping == 0 and tax == 0:
            notes.append(
                "Buyer-paid shipping and sales tax were left at $0.00, so processing is calculated on the item price only."
            )
        return _Quote(price, processing_base, lines, total, net, formula, tuple(notes), "standard")

    @staticmethod
    def _facebook(price: Decimal, shipping: Decimal, tax: Decimal, config: dict, fulfillment: str) -> _Quote:
        rates = config["platforms"]["facebook_marketplace"]
        verify = rates["verify_note"]
        mode = fulfillment if fulfillment == "shipped" else "local_pickup"
        if mode == "local_pickup":
            fee = Decimal("0.00")
            lines = (FeeLine("Local pickup selling fee", fee),)
            formula = (
                f"Fulfillment is local pickup. Selling fee {Money.format(fee)} "
                f"(Facebook does not charge for local pickup). "
                f"Total fee {Money.format(fee)}. "
                f"Net {Money.format(price)} − {Money.format(fee)} = {Money.format(price)}."
            )
            notes = (
                verify,
                "This quote uses local pickup. Switch fulfillment to shipped to apply shipped_percent and shipped_minimum.",
            )
            return _Quote(price, price, lines, fee, price, formula, notes, "local_pickup")
        base = price + shipping + tax
        percent = Decimal(rates["shipped_percent"])
        minimum = Decimal(rates["shipped_minimum"])
        percent_fee = Money.quantize(base * percent)
        if percent_fee >= minimum:
            fee = percent_fee
            lines = (
                FeeLine(f"Shipped selling fee {Money.percent_label(percent)} × {Money.format(base)}", fee),
            )
            choice = (
                f"the greater of {Money.percent_label(percent)} × {Money.format(base)} = {Money.format(percent_fee)} "
                f"and the {Money.format(minimum)} minimum, so {Money.format(fee)}"
            )
        else:
            fee = minimum
            lines = (FeeLine(f"Shipped selling fee minimum {Money.format(minimum)}", fee),)
            choice = (
                f"the greater of {Money.percent_label(percent)} × {Money.format(base)} = {Money.format(percent_fee)} "
                f"and the {Money.format(minimum)} minimum, so {Money.format(fee)}"
            )
        net = Money.quantize(price - fee)
        formula = (
            f"Fulfillment is shipped checkout. Fee base {Money.format(base)} "
            f"({FeeCalculator._parts(price, shipping, tax, include_tax=True)}). "
            f"Selling fee is {choice}. "
            f"Total fee {Money.format(fee)}. "
            f"Net {Money.format(price)} − {Money.format(fee)} = {Money.format(net)}."
        )
        notes = [verify, "The shipped rate is flagged in config/fees.yaml. Confirm it in Facebook checkout before you rely on this net."]
        notes.extend(
            FeeCalculator._shipping_tax_notes(
                "Facebook Marketplace", shipping, tax, charges_shipping=True, charges_tax=True
            )
        )
        notes.append("Net is the item price minus the selling fee. Buyer-paid shipping and sales tax are not treated as profit.")
        return _Quote(price, base, lines, fee, net, formula, tuple(notes), "shipped")

    @staticmethod
    def _base_sentence(price: Decimal, shipping: Decimal, tax: Decimal) -> str:
        total = price + shipping + tax
        return f"Fee base {Money.format(total)} ({FeeCalculator._parts(price, shipping, tax, include_tax=True)})."

    @staticmethod
    def _parts(price: Decimal, shipping: Decimal, tax: Decimal, *, include_tax: bool) -> str:
        bits = [f"item {Money.format(price)}"]
        if shipping > 0:
            bits.append(f"buyer-paid shipping {Money.format(shipping)}")
        if include_tax and tax > 0:
            bits.append(f"sales tax {Money.format(tax)}")
        if len(bits) == 1:
            return bits[0]
        return " + ".join(bits)

    @staticmethod
    def _shipping_tax_notes(
        platform: str,
        shipping: Decimal,
        tax: Decimal,
        *,
        charges_shipping: bool,
        charges_tax: bool,
    ) -> list[str]:
        notes = []
        if charges_shipping and shipping == 0:
            notes.append(
                f"Buyer-paid shipping was left at $0.00. Add it if the buyer will pay you for shipping; {platform} includes that amount in the fee base."
            )
        elif charges_shipping and shipping > 0:
            notes.append(f"Buyer-paid shipping is included in {platform}'s fee base and is not added to the payout.")
        if charges_tax and tax == 0:
            notes.append(
                f"Sales tax was left at $0.00. Add the tax collected if {platform} will charge its fee on it."
            )
        elif charges_tax and tax > 0:
            notes.append(f"Sales tax is included in {platform}'s fee base and is not part of the payout.")
        return notes
