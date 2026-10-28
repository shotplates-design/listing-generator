from decimal import Decimal

from listing_generator.descriptions import DescriptionBuilder
from listing_generator.generator import ListingGenerator
from listing_generator.models import ClothingItem
from listing_generator.polish import ListingPolish


def test_description_has_measurements_and_honest_condition(hoodie):
    text = DescriptionBuilder.build(hoodie, "ebay")
    assert "Measurements" in text
    assert "Not included." in text
    assert "Small hole near the left hem" in text
    assert "Pre-owned — Good" in text
    assert "22" not in text
    assert "smoke" not in text.lower()


def test_facebook_description_is_plain(hoodie):
    text = DescriptionBuilder.build(hoodie, "facebook_marketplace")
    assert "Used - Good" in text
    assert "Small hole near the left hem" in text
    assert "#" not in text
    assert "Measurements" in text


def test_facebook_poor_condition_is_not_upgraded_silently():
    item = ClothingItem(condition="poor", item_type="hoodie")
    text = DescriptionBuilder.build(item, "facebook_marketplace")
    assert "Used - Fair" in text
    assert "Poor" in text


def test_measurements_are_copied_when_the_seller_typed_them():
    item = ClothingItem(measurements={"pit_to_pit": "22 in", "length": "27 in"})
    text = DescriptionBuilder.build(item, "facebook_marketplace")
    assert "Pit to pit: 22 in" in text
    assert "Length: 27 in" in text
    assert "Not included." not in text


def test_no_price_is_not_invented():
    listings = {row.platform: row for row in ListingGenerator.generate(ClothingItem(brand="Nike"))}
    facebook = listings["facebook_marketplace"]
    assert facebook.list_price is None
    assert facebook.fee is None
    assert "not estimated from the photos" in facebook.price_rationale


def test_cost_basis_markup_needs_a_condition():
    item = ClothingItem(cost_basis=Decimal("20"), condition="good")
    listing = {row.platform: row for row in ListingGenerator.generate(item)}["ebay"]
    assert listing.list_price == Decimal("27")
    assert "1.35" in listing.price_rationale
    assert listing.fee.net == Decimal("27") - listing.fee.total_fee


def test_polish_off_does_not_call_a_provider(monkeypatch, hoodie):
    monkeypatch.delenv("LISTING_LLM_POLISH", raising=False)

    def explode(_prompt):
        raise AssertionError("polish should stay off")

    first = ListingGenerator.generate(hoodie)
    assert all(row.polish == "off" for row in first)
    assert ListingPolish.apply(tuple(first), completer=explode) == tuple(first)


def test_polish_reenforces_the_title_limit(monkeypatch, hoodie):
    monkeypatch.delenv("LISTING_LLM_POLISH", raising=False)
    drafts = ListingGenerator.generate(hoodie)
    monkeypatch.setenv("LISTING_LLM_POLISH", "1")
    monkeypatch.setenv("VISION_PROVIDER", "mock")

    def completer(_prompt):
        return json_of({row.platform: {"title": "Z" * 500, "description": row.description} for row in drafts})

    polished = ListingPolish.apply(tuple(drafts), completer=completer)
    assert all(row.polish == "applied" for row in polished)
    assert all(len(row.title) <= row.title_limit for row in polished)


def test_polish_strips_facebook_hashtags_and_keeps_title_limits(monkeypatch, hoodie):
    monkeypatch.delenv("LISTING_LLM_POLISH", raising=False)
    drafts = ListingGenerator.generate(hoodie)
    monkeypatch.setenv("LISTING_LLM_POLISH", "1")

    def completer(_prompt):
        payload = {}
        for row in drafts:
            if row.platform == "facebook_marketplace":
                payload[row.platform] = {
                    "title": "#vintage " + ("Z" * 500),
                    "description": row.description + "\n#forsale #hoodie",
                }
            else:
                payload[row.platform] = {"title": row.title, "description": row.description}
        return json_of(payload)

    polished = ListingPolish.apply(tuple(drafts), completer=completer)
    facebook = next(row for row in polished if row.platform == "facebook_marketplace")
    depop = next(row for row in polished if row.platform == "depop")
    assert facebook.polish == "applied"
    assert "#" not in facebook.title
    assert "#" not in facebook.description
    assert 0 < len(facebook.title) <= facebook.title_limit
    assert all(len(row.title) <= row.title_limit for row in polished)
    assert "#" in depop.description


def json_of(payload) -> str:
    import json

    return json.dumps(payload)
