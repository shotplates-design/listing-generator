"""Provider interface. Gemini is the default; an OpenAI-compatible server is optional."""

from __future__ import annotations

from abc import ABC, abstractmethod

from listing_generator.vision.images import PreparedImage


class VisionProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def analyze(self, images: list[PreparedImage]) -> dict:
        """Return the raw JSON object from the model. Do not fill blanks."""

    @abstractmethod
    def complete_text(self, prompt: str) -> str:
        """Used only when LISTING_LLM_POLISH=1."""
