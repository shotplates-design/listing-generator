import json
from io import BytesIO

import pytest
from PIL import Image

from listing_generator.descriptions import DescriptionBuilder
from listing_generator.generator import ListingGenerator
from listing_generator.models import Platforms
from listing_generator.vision.factory import VisionProviders
from listing_generator.vision.gemini import GeminiVisionProvider
from listing_generator.vision.images import ImagePrep
from listing_generator.vision.mock import MockVisionProvider
from listing_generator.vision.openai_compatible import OpenAICompatibleVisionProvider
from listing_generator.vision.parser import ExtractionParser
from listing_generator.vision.sample import SampleReading


def test_parser_blanks_unsure_fields_and_every_measurement():
    result = ExtractionParser.parse(SampleReading.payload(), provider="mock", model="mock-fixture", photo_count=4)
    item = result.item
    assert item.brand == "Nike"
    assert item.item_type == "hoodie"
    assert item.size_tagged == "M"
    assert item.color == "navy"
    assert item.material == "cotton blend"
    assert item.field_confidence["material"] == "medium"
    assert "uncertain" in item.field_flags["material"].lower()
    assert item.condition == ""
    assert item.field_confidence["condition"] == "none"
    assert item.gender_department == ""
    assert item.measurements == {}
    assert "cannot be read from photos" in item.field_flags["measurements"].lower()
    assert item.flaws == "Small hole near the left hem"
    discarded = {row.field: row.value for row in result.discarded}
    assert "22 in" in discarded["measurements"]
    assert "womens" in discarded["gender_department"]
    blob = " ".join(DescriptionBuilder.build(item, platform) for platform in Platforms.ORDER)
    assert "22" not in blob
    assert "27" not in blob


def test_low_confidence_and_placeholder_and_bare_string_are_dropped():
    payload = {
        "brand": "Nike",
        "color": {"value": "unknown", "confidence": "high", "evidence": ""},
        "item_type": {"value": "coat", "confidence": "low", "evidence": "maybe"},
    }
    result = ExtractionParser.parse(payload, provider="mock", model="mock", photo_count=1)
    assert result.item.brand == ""
    assert result.item.color == ""
    assert result.item.item_type == ""
    brand = next(row for row in result.discarded if row.field == "brand")
    assert brand.confidence == "none"
    assert "confidence" in brand.reason.lower()


def test_text_only_ruler_claim_drops_measurements():
    payload = {
        "measurements": {
            "value": {"pit_to_pit": "23 in", "length": "27 in"},
            "confidence": "high",
            "evidence": "a ruler, tape measure, measuring tape, and yardstick are visible; photo_index 1 visible yes",
        }
    }
    result = ExtractionParser.parse(payload, provider="mock", model="mock", photo_count=6)
    assert result.item.measurements == {}
    assert result.item.field_confidence["measurements"] == "none"
    flag = result.item.field_flags["measurements"].lower()
    assert "cannot be read from photos" in flag
    assert "ruler" in flag
    assert "photo" in flag
    dropped = next(row for row in result.discarded if row.field == "measurements")
    assert "23 in" in dropped.value
    assert "27 in" in dropped.value
    assert "photo" in dropped.reason.lower()


def test_structured_visible_ruler_keeps_measurements():
    claims = (
        {"photo_index": 2, "visible": True},
        {"photo_index": "2", "visible": "yes"},
    )
    for scale in claims:
        payload = {
            "measurements": {
                "value": {"pit_to_pit": "23 in", "length": "27 in"},
                "confidence": "high",
                "evidence": "the second photo shows the marks across the chest and the hem",
                "scale": scale,
            }
        }
        result = ExtractionParser.parse(payload, provider="mock", model="mock", photo_count=3)
        assert result.item.measurements == {"pit_to_pit": "23 in", "length": "27 in"}
        assert result.item.field_confidence["measurements"] == "high"
        assert "measurements" not in result.item.field_flags
        assert not any(row.field == "measurements" for row in result.discarded)
        blob = " ".join(DescriptionBuilder.build(result.item, platform) for platform in Platforms.ORDER)
        assert "Pit to pit: 23 in" in blob
        assert "Length: 27 in" in blob


def test_photo_index_outside_the_photo_count_is_dropped():
    def payload(index: object) -> dict:
        return {
            "measurements": {
                "value": {"pit_to_pit": "23 in", "length": "27 in"},
                "confidence": "high",
                "evidence": "marks across the chest and the hem",
                "scale": {"photo_index": index, "visible": True},
            }
        }

    for index in (6, 99, "6"):
        result = ExtractionParser.parse(payload(index), provider="mock", model="mock", photo_count=6)
        assert result.item.measurements == {}
        assert result.item.field_confidence["measurements"] == "none"
        flag = result.item.field_flags["measurements"].lower()
        assert "cannot be read from photos" in flag
        assert "ruler" in flag
        assert "photo" in flag
        dropped = next(row for row in result.discarded if row.field == "measurements")
        assert "23 in" in dropped.value
        assert "27 in" in dropped.value
        assert "photo" in dropped.reason.lower()

    empty = ExtractionParser.parse(payload(0), provider="mock", model="mock", photo_count=0)
    assert empty.item.measurements == {}
    assert "cannot be read from photos" in empty.item.field_flags["measurements"].lower()
    assert any(row.field == "measurements" for row in empty.discarded)

    kept = ExtractionParser.parse(payload(5), provider="mock", model="mock", photo_count=6)
    assert kept.item.measurements == {"pit_to_pit": "23 in", "length": "27 in"}
    assert "measurements" not in kept.item.field_flags
    assert not any(row.field == "measurements" for row in kept.discarded)


def test_measurements_without_a_ruler_are_dropped():
    payloads = [
        {
            "measurements": {
                "value": {"pit_to_pit": "23 in", "length": "27 in"},
                "confidence": "high",
                "evidence": "estimated from how the hoodie looks on the floor",
            }
        },
        {
            "measurements": {
                "value": {"pit_to_pit": "23 in", "length": "27 in"},
                "confidence": "high",
                "evidence": "flat lay",
                "scale": {"photo_index": 1, "visible": False},
            }
        },
        {
            "measurements": {
                "value": {"pit_to_pit": "23 in", "length": "27 in"},
                "confidence": "high",
                "evidence": "flat lay",
                "scale": {"photo_index": 1, "visible": "no"},
            }
        },
        {
            "measurements": {
                "value": {"pit_to_pit": "23 in"},
                "confidence": "high",
                "evidence": "flat lay",
                "scale": {"visible": True},
            }
        },
        {
            "measurements": {
                "value": {"pit_to_pit": "23 in"},
                "confidence": "high",
                "evidence": "flat lay",
                "scale": {"photo_index": True, "visible": True},
            }
        },
    ]
    for payload in payloads:
        result = ExtractionParser.parse(payload, provider="mock", model="mock", photo_count=6)
        assert result.item.measurements == {}
        assert result.item.field_confidence["measurements"] == "none"
        flag = result.item.field_flags["measurements"].lower()
        assert "cannot be read from photos" in flag
        assert "ruler" in flag
        dropped = next(row for row in result.discarded if row.field == "measurements")
        assert "23 in" in dropped.value
        assert "photo" in dropped.reason.lower()


def test_approximate_flag_without_a_ruler_does_not_keep_measurements():
    payload = {
        "measurements": {
            "value": {"pit_to_pit": "23 in", "length": "27 in"},
            "confidence": "high",
            "approximate": True,
            "evidence": "estimated from how the hoodie looks on the floor",
        }
    }
    result = ExtractionParser.parse(payload, provider="mock", model="mock", photo_count=6)
    assert result.item.measurements == {}
    assert result.item.field_confidence["measurements"] == "none"
    dropped = next(row for row in result.discarded if row.field == "measurements")
    assert "23 in" in dropped.value
    assert "27 in" in dropped.value
    assert dropped.confidence == "high"


def test_mock_provider_is_what_tests_call():
    provider = MockVisionProvider()
    result = ExtractionParser.parse(provider.analyze([]), provider=provider.name, model=provider.model, photo_count=4)
    listings = ListingGenerator.generate(result.item)
    assert len(listings) == 6
    assert all("22" not in listing.description for listing in listings)


def test_gemini_request_keeps_the_key_out_of_the_url_and_body():
    image = ImagePrep.prepare("tag.jpg", _png())
    provider = GeminiVisionProvider(api_key="super-secret-key", model="gemini-2.5-flash")
    url, headers, payload = provider.build_request([image])
    assert "super-secret-key" not in url
    assert "key=" not in url
    assert headers["x-goog-api-key"] == "super-secret-key"
    assert "super-secret-key" not in json.dumps(payload)
    assert payload["generationConfig"]["temperature"] == 0


def test_openai_request_uses_bearer_header():
    image = ImagePrep.prepare("tag.jpg", _png())
    provider = OpenAICompatibleVisionProvider(api_key="sk-test", model="vision-model", base_url="https://example.invalid/v1")
    url, headers, payload = provider.build_request([image])
    assert url == "https://example.invalid/v1/chat/completions"
    assert headers["Authorization"] == "Bearer sk-test"
    assert "sk-test" not in json.dumps(payload)
    assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_describe_does_not_reveal_the_key(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key")
    assert "super-secret-key" not in json.dumps(VisionProviders.describe())


def test_missing_gemini_key_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(Exception) as caught:
        VisionProviders.from_env()
    assert "GEMINI_API_KEY" in str(caught.value)
    assert "super-secret" not in str(caught.value)


def test_image_prep_shrinks_the_long_edge():
    prepared = ImagePrep.prepare("wide.png", _png(width=3000, height=20))
    image = Image.open(BytesIO(prepared.data))
    assert prepared.mime_type == "image/jpeg"
    assert max(image.size) <= ImagePrep.MAX_EDGE


def _png(width=40, height=40) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), (10, 20, 40)).save(buffer, format="PNG")
    return buffer.getvalue()
