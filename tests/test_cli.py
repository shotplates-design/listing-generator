import json
from io import BytesIO
from pathlib import Path

from PIL import Image

from listing_generator.cli import CommandLine
from listing_generator.export import ListingExport


def test_cli_analyze_and_generate_round_trip(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    photo = tmp_path / "front.png"
    buffer = BytesIO()
    Image.new("RGB", (30, 30), (20, 30, 40)).save(buffer, format="PNG")
    photo.write_bytes(buffer.getvalue())
    review = tmp_path / "review.json"
    assert CommandLine.main(["analyze", str(photo), "--role", "front", "--output", str(review), "--provider", "mock"]) == 0
    payload = json.loads(review.read_text(encoding="utf-8"))
    assert payload["item"]["brand"] == "Nike"
    assert payload["item"]["measurements"] == {}
    assert payload["photos"][0]["role"] == "front"
    listing = tmp_path / "listing.json"
    assert CommandLine.main(["generate", str(review), "--format", "json", "--output", str(listing), "--item-id", "cli-1"]) == 0
    document = json.loads(listing.read_text(encoding="utf-8"))
    ListingExport.validate(document)
    facebook = document["listings"]["facebook_marketplace"]
    assert facebook["price"] is None
    assert facebook["fees"] is None
    assert "#" not in facebook["description"]
    assert "22" not in document["listings"]["depop"]["description"]
    assert Path(listing).exists()
    capsys.readouterr()
