"""Offline provider for tests and the local demo. It never reads the photos."""

from __future__ import annotations

from listing_generator.vision.base import VisionProvider
from listing_generator.vision.images import PreparedImage
from listing_generator.vision.sample import SampleReading


class MockVisionProvider(VisionProvider):
    def __init__(self) -> None:
        self.name = "mock"
        self.model = "mock-fixture"

    def analyze(self, images: list[PreparedImage]) -> dict:
        return SampleReading.payload()

    def complete_text(self, prompt: str) -> str:
        return prompt
