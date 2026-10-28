from listing_generator.fees import FeeSchedule
from listing_generator.generator import ListingGenerator
from listing_generator.models import ClothingItem, Platforms
from listing_generator.titles import TitleBuilder


def test_titles_stay_inside_each_platform_limit(hoodie):
    listings = {listing.platform: listing for listing in ListingGenerator.generate(hoodie)}
    limits = FeeSchedule.load()["title_limits"]
    assert set(listings) == set(Platforms.ORDER)
    for platform, listing in listings.items():
        assert len(listing.title) <= listing.title_limit
        assert listing.title_limit == limits[platform]
        assert listing.title


def test_known_titles(hoodie):
    assert TitleBuilder.ebay(hoodie) == "Nike Hoodie Men's Size M Navy Cotton Blend 90s Athletic Good"
    assert TitleBuilder.poshmark(hoodie) == "Nike Hoodie Men's Size M Navy Cotton Blend 90s Athletic"
    assert TitleBuilder.mercari(hoodie) == "Nike Hoodie Men's Size M Navy Cotton Blend"
    assert TitleBuilder.depop(hoodie) == "navy cotton blend nike hoodie, men's, size m — 90s athletic"
    assert TitleBuilder.whatnot(hoodie) == "Nike · Hoodie · M · Navy"
    assert TitleBuilder.facebook(hoodie) == "Nike Men's Hoodie Size M Navy"


def test_long_fields_are_cut_to_the_limit():
    item = ClothingItem(
        brand="A" * 300,
        item_type="B" * 300,
        size_tagged="C" * 80,
        color="D" * 80,
        material="E" * 80,
        style_era="F" * 80,
        condition="good",
        gender_department="mens",
    )
    for platform in Platforms.ORDER:
        title = TitleBuilder.for_platform(platform, item)
        assert 0 < len(title) <= TitleBuilder.limit(platform)
        assert not title.endswith(" ")


def test_facebook_title_has_no_hashtags(hoodie):
    title = TitleBuilder.facebook(hoodie)
    description_source = title
    assert "#" not in description_source
    assert len(title) <= 100
    assert title.startswith("Nike")


def test_empty_item_still_has_a_title():
    item = ClothingItem()
    for platform in Platforms.ORDER:
        title = TitleBuilder.for_platform(platform, item)
        assert title
        assert len(title) <= TitleBuilder.limit(platform)
