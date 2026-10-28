from decimal import Decimal

from listing_generator.fees import FeeCalculator, FeeSchedule


def _fee(platform, price, **kwargs):
    return FeeCalculator.calculate(platform, Decimal(price), **kwargs)


def test_shipped_rates_match_published_examples():
    ebay = _fee("ebay", "25")
    assert ebay.total_fee == Decimal("3.80")
    assert ebay.net == Decimal("21.20")
    assert ebay.formula == (
        "Fee base $25.00 (item $25.00). Final value fee 13.6% × $25.00 = $3.40. "
        "Per-order fee $0.40 because the fee base is over $10.00. "
        "Total fee $3.80. Net $25.00 − $3.80 = $21.20."
    )

    taxed = _fee("ebay", "25", sales_tax=Decimal("1.50"))
    assert taxed.total_fee == Decimal("4.00")
    assert taxed.net == Decimal("21.00")

    small = _fee("ebay", "10")
    assert small.total_fee == Decimal("1.66")
    assert small.net == Decimal("8.34")

    assert _fee("poshmark", "14.99").total_fee == Decimal("2.95")
    assert _fee("poshmark", "14.99").net == Decimal("12.04")
    assert _fee("poshmark", "15").total_fee == Decimal("3.00")
    assert _fee("poshmark", "15").net == Decimal("12.00")
    assert _fee("poshmark", "40").total_fee == Decimal("8.00")
    assert _fee("poshmark", "40").net == Decimal("32.00")
    assert _fee("poshmark", "50").net == Decimal("40.00")

    depop = _fee("depop", "50")
    assert depop.total_fee == Decimal("2.10")
    assert depop.net == Decimal("47.90")

    mercari = _fee("mercari", "50")
    assert mercari.total_fee == Decimal("5.00")
    assert mercari.net == Decimal("45.00")
    with_ship = _fee("mercari", "40", buyer_shipping=Decimal("8"))
    assert with_ship.total_fee == Decimal("4.80")
    assert with_ship.net == Decimal("35.20")

    whatnot = _fee("whatnot", "50")
    assert whatnot.total_fee == Decimal("5.75")
    assert whatnot.net == Decimal("44.25")


def test_half_up_rounding_not_bankers():
    quote = _fee("mercari", "1.25")
    assert quote.total_fee == Decimal("0.13")
    assert quote.net == Decimal("1.12")


def test_ebay_category_profiles():
    shoes = _fee("ebay", "150", item_type="running shoes")
    assert shoes.total_fee == Decimal("12.00")
    assert shoes.net == Decimal("138.00")
    assert shoes.lines[-1].label.startswith("Final value fee 8%")

    bag = _fee("ebay", "100", item_type="leather handbag")
    assert bag.total_fee == Decimal("15.40")
    assert bag.net == Decimal("84.60")

    high = _fee("ebay", "7600")
    assert high.total_fee == Decimal("1022.75")
    assert high.net == Decimal("6577.25")


def test_facebook_local_pickup_is_free_and_shipped_fee_is_flagged():
    rates = FeeSchedule.load()["platforms"]["facebook_marketplace"]
    assert rates["shipped_percent"] == "0.10"
    assert rates["shipped_minimum"] == "0.80"
    assert "Verify" in rates["verify_note"]

    local = _fee("facebook_marketplace", "40")
    assert local.total_fee == Decimal("0.00")
    assert local.net == Decimal("40.00")
    assert rates["verify_note"] in local.notes
    assert "local pickup" in local.formula

    shipped = _fee("facebook_marketplace", "50", facebook_fulfillment="shipped")
    assert shipped.total_fee == Decimal("5.00")
    assert shipped.net == Decimal("45.00")
    assert shipped.formula == (
        "Fulfillment is shipped checkout. Fee base $50.00 (item $50.00). "
        "Selling fee is the greater of 10% × $50.00 = $5.00 and the $0.80 minimum, so $5.00. "
        "Total fee $5.00. Net $50.00 − $5.00 = $45.00."
    )
    assert rates["verify_note"] in shipped.notes

    minimum = _fee("facebook_marketplace", "5", facebook_fulfillment="shipped")
    assert minimum.total_fee == Decimal("0.80")
    assert minimum.net == Decimal("4.20")

    boundary = _fee("facebook_marketplace", "8", facebook_fulfillment="shipped")
    assert boundary.total_fee == Decimal("0.80")

    with_shipping = _fee(
        "facebook_marketplace",
        "40",
        buyer_shipping=Decimal("8"),
        facebook_fulfillment="shipped",
    )
    assert with_shipping.fee_base == Decimal("48.00")
    assert with_shipping.total_fee == Decimal("4.80")
    assert with_shipping.net == Decimal("35.20")


def test_price_for_net_is_the_smallest_cent():
    price = FeeCalculator.price_for_net("poshmark", Decimal("12.04"))
    assert price == Decimal("14.99")
    assert FeeCalculator.calculate("poshmark", price).net >= Decimal("12.04")
    assert FeeCalculator.calculate("poshmark", price - Decimal("0.01")).net < Decimal("12.04")

    shipped = FeeCalculator.price_for_net(
        "facebook_marketplace",
        Decimal("45.00"),
        facebook_fulfillment="shipped",
    )
    assert shipped == Decimal("50.00")
    local = FeeCalculator.price_for_net("facebook_marketplace", Decimal("40.00"))
    assert local == Decimal("40.00")
