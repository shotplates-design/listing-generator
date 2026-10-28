import os
from io import BytesIO

import pytest
from PIL import Image

from listing_generator.export import ListingExport
from listing_generator.fixtures import HoodieFixture
from listing_generator.generator import ListingGenerator
from listing_generator.models import PhotoRef, Platforms
from listing_generator.vision.errors import VisionError
from listing_generator.vision.factory import VisionProviders
from listing_generator.vision.images import ImagePrep
from listing_generator.vision.parser import ExtractionParser


def test_fixture_photos_are_downscaled():
    assert len(HoodieFixture.manifest()) == 6
    for name, data, role in HoodieFixture.manifest():
        assert role in {"front", "back", "tag", "flaw", "detail"}
        image = Image.open(BytesIO(data))
        assert max(image.size) <= 1600
        assert len(data) < 900_000
        assert name.endswith(".jpg")


def test_recorded_reading_matches_the_hoodie_and_keeps_ruler_measurements():
    recorded = HoodieFixture.vision_response()["measurements"]
    assert "ruler" in recorded["evidence"].lower()
    assert recorded["value"]["pit_to_pit"] == "23 in"
    assert recorded["value"]["length"] == "27 in"
    result = ExtractionParser.parse(
        HoodieFixture.vision_response(),
        provider="recorded",
        model="assc-hoodie-v1",
    )
    item = result.item
    assert item.brand == "Anti Social Social Club"
    assert item.item_type == "hoodie"
    assert item.color == "blue"
    assert item.size_tagged == "L"
    assert "100%" in item.material
    assert "cotton" in item.material.lower()
    assert item.origin == "Made in USA"
    assert item.style_era == "Instant Gratification"
    assert item.condition == ""
    assert item.gender_department == ""
    assert item.measurements["pit_to_pit"] == "23 in"
    assert item.measurements["length"] == "27 in"
    assert "approximate" not in item.field_flags.get("measurements", "").lower()
    assert not any(row.field == "measurements" for row in result.discarded)

    photos = [
        PhotoRef(name, role, index)
        for index, (name, _data, role) in enumerate(HoodieFixture.manifest())
    ]
    listings = ListingGenerator.generate(item)
    document = ListingExport.build(
        item,
        listings,
        photos,
        discarded=result.discarded,
        item_id="assc-hoodie",
        created_at="2026-10-28T13:00:00Z",
    )
    assert set(document["listings"]) == set(Platforms.ORDER)
    for listing in document["listings"].values():
        assert len(listing["title"]) <= listing["title_limit"]
        assert "anti social social club" in listing["title"].lower()
        assert "Anti Social Social Club" in listing["description"]
        assert "Instant Gratification" in listing["description"]
        assert "Made in USA" in listing["description"] or "Made In USA" in listing["description"]
        assert "Pit to pit: 23 in" in listing["description"]
        assert "Length: 27 in" in listing["description"]
        assert "approximate" not in listing["description"].lower()
        assert "not set" not in listing["description"].lower()
    facebook = document["listings"]["facebook_marketplace"]
    assert "#" not in facebook["title"]
    assert "#" not in facebook["description"]
    assert len(facebook["title"]) <= 100
    assert "L" in facebook["title"]
    depop = document["listings"]["depop"]
    assert "#antisocialsocialclub" in depop["tags"] or any("social" in tag for tag in depop["tags"])


@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY is not set")
def test_live_gemini_once_on_the_hoodie_photos():
    """One real call when a key is present. Safety checks only; the recorded JSON is the fixture."""
    prepared = ImagePrep.prepare_many([(name, data) for name, data, _role in HoodieFixture.manifest()])
    provider = VisionProviders.from_env()
    if provider.name != "gemini":
        pytest.skip("VISION_PROVIDER is not gemini")
    try:
        payload = provider.analyze(prepared)
    except VisionError as exc:
        pytest.fail(f"Live Gemini call failed: {exc}")
    result = ExtractionParser.parse(payload, provider=provider.name, model=provider.model)
    if result.item.measurements:
        raw = payload.get("measurements") if isinstance(payload, dict) else {}
        evidence = str((raw or {}).get("evidence") or "").lower() if isinstance(raw, dict) else ""
        assert "ruler" in evidence or "tape" in evidence or (isinstance(raw, dict) and raw.get("approximate") is True)
    joined = " ".join(
        [
            result.item.brand,
            result.item.item_type,
            result.item.color,
            result.item.material,
            result.item.origin,
            result.item.style_era,
            result.item.size_tagged,
        ]
    ).lower()
    assert "hoodie" in joined or "social" in joined or "cotton" in joined or "blue" in joined
