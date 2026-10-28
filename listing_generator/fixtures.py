"""The included Anti Social Social Club hoodie photos and their recorded reading."""

from __future__ import annotations

import json
from pathlib import Path


class HoodieFixture:
    """Downscaled photos of one real hoodie, plus the vision JSON the tests replay."""

    FILES = (
        ("01-front.jpg", "front"),
        ("02-back.jpg", "back"),
        ("03-print.jpg", "detail"),
        ("04-size-stamp.jpg", "tag"),
        ("05-neck-tag.jpg", "tag"),
        ("06-ruler.jpg", "detail"),
    )

    @staticmethod
    def directory() -> Path:
        return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "assc_hoodie"

    @staticmethod
    def manifest() -> list[tuple[str, bytes, str]]:
        root = HoodieFixture.directory()
        return [(name, (root / name).read_bytes(), role) for name, role in HoodieFixture.FILES]

    @staticmethod
    def images() -> list[tuple[str, bytes]]:
        return [(name, data) for name, data, _role in HoodieFixture.manifest()]

    @staticmethod
    def vision_response() -> dict:
        path = HoodieFixture.directory() / "vision_response.json"
        return json.loads(path.read_text(encoding="utf-8"))
