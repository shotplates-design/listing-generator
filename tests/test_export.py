import json

import pytest

from listing_generator.export import ExportError, ListingExport
from listing_generator.generator import ListingGenerator
from listing_generator.models import PhotoRef, Platforms
from listing_generator.text import Conditions
from listing_generator.vision.parser import ExtractionParser
from listing_generator.vision.sample import SampleReading


def _document(item, **kwargs):
    listings = ListingGenerator.generate(item)
    return ListingExport.build(
        item,
        listings,
        [PhotoRef("front.jpg", "front", 0), PhotoRef("tag.jpg", "tag", 1)],
        item_id="item-1",
        created_at="2026-10-28T13:00:00Z",
        **kwargs,
    )


def test_every_export_matches_schema_v1(hoodie):
    document = _document(hoodie)
    ListingExport.validate(document)
    assert document["schema_version"] == "1.0.0"
    assert set(document["listings"]) == set(Platforms.ORDER)
    facebook = document["listings"]["facebook_marketplace"]
    assert facebook["title"]
    assert len(facebook["title"]) <= facebook["title_limit"] <= 100
    assert "#" not in facebook["title"]
    assert "#" not in facebook["description"]
    assert "Measurements" in facebook["description"]
    assert facebook["item_specifics"]["Condition"] == "Used - Good"
    assert facebook["fees"]["total"] == "0.00"
    assert facebook["net"] == "40.00"
    assert document["pricing_inputs"]["facebook_fulfillment"] == "local_pickup"
    assert any("Verify" in note for note in facebook["fees"]["notes"])
    for listing in document["listings"].values():
        assert len(listing["title"]) <= listing["title_limit"]
        assert len(listing["description"]) <= listing["description_limit"]


def test_shipped_facebook_fee_is_in_the_export(hoodie):
    hoodie.facebook_fulfillment = "shipped"
    document = _document(hoodie)
    facebook = document["listings"]["facebook_marketplace"]
    assert facebook["fees"]["total"] == "4.00"
    assert facebook["net"] == "36.00"
    assert "Verify" in facebook["price_rationale"]
    assert document["pricing_inputs"]["facebook_fulfillment"] == "shipped"


def test_schema_rejects_a_document_missing_facebook(hoodie):
    document = _document(hoodie)
    del document["listings"]["facebook_marketplace"]
    with pytest.raises(ExportError):
        ListingExport.validate(document)


def test_sample_reading_round_trip_keeps_measurements_out(hoodie):
    result = ExtractionParser.parse(SampleReading.payload(), provider="mock", model="mock-fixture")
    document = ListingExport.build(
        result.item,
        ListingGenerator.generate(result.item),
        [PhotoRef("sample-front.png", "front", 0)],
        discarded=result.discarded,
        item_id="sample",
        created_at="2026-10-28T13:00:00Z",
    )
    assert document["attributes"]["measurements"] == {}
    assert document["attributes"]["department"] == ""
    assert document["attributes"]["condition"] == ""
    assert document["field_confidence"]["measurements"] == "none"
    assert "22 in" not in document["listings"]["ebay"]["description"]
    restored, photos, discarded = ListingExport.item_from_document(document)
    assert restored.brand == "Nike"
    assert restored.measurements == {}
    assert photos[0].role == "front"
    assert any(row.field == "measurements" for row in discarded)
    again = ListingExport.build(
        restored,
        ListingGenerator.generate(restored),
        photos,
        discarded=discarded,
        item_id="sample",
        created_at="2026-10-28T13:00:00Z",
    )
    assert again["listings"]["facebook_marketplace"]["title"] == document["listings"]["facebook_marketplace"]["title"]


def test_facebook_condition_labels():
    expected = {
        "new_with_tags": "New",
        "new_without_tags": "Used - Like New",
        "excellent": "Used - Like New",
        "good": "Used - Good",
        "fair": "Used - Fair",
        "poor": "Used - Fair",
    }
    for key, label in expected.items():
        assert Conditions.platform_label(key, "facebook_marketplace") == label


def test_schema_version_constant_matches_the_file():
    schema = json.loads(ListingExport.schema_path().read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == ListingExport.SCHEMA_VERSION
    assert "facebook_marketplace" in schema["$defs"]["listings"]["required"]
