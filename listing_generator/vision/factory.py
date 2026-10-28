"""Selects the vision provider from the environment. The default is Gemini."""

from __future__ import annotations

import os

from listing_generator.vision.base import VisionProvider
from listing_generator.vision.errors import VisionError
from listing_generator.vision.gemini import GeminiVisionProvider
from listing_generator.vision.mock import MockVisionProvider
from listing_generator.vision.openai_compatible import OpenAICompatibleVisionProvider


class VisionProviders:
    @staticmethod
    def from_env() -> VisionProvider:
        name = os.environ.get("VISION_PROVIDER", "gemini").strip().lower() or "gemini"
        if name == "mock":
            return MockVisionProvider()
        if name == "openai":
            return OpenAICompatibleVisionProvider(
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                model=os.environ.get("OPENAI_MODEL", ""),
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
        if name == "gemini":
            return GeminiVisionProvider(
                api_key=os.environ.get("GEMINI_API_KEY", ""),
                model=os.environ.get("VISION_MODEL", GeminiVisionProvider.DEFAULT_MODEL),
                base_url=os.environ.get("GEMINI_API_BASE", GeminiVisionProvider.DEFAULT_BASE),
            )
        raise VisionError("VISION_PROVIDER must be gemini, openai, or mock.")

    @staticmethod
    def describe() -> dict[str, str | bool]:
        name = os.environ.get("VISION_PROVIDER", "gemini").strip().lower() or "gemini"
        polish = os.environ.get("LISTING_LLM_POLISH", "0").strip().lower() in {"1", "true", "yes", "on"}
        if name == "mock":
            return {
                "provider": "mock",
                "model": "mock-fixture",
                "key_configured": True,
                "polish": polish,
                "note": "Offline sample provider. It does not look at the photos.",
            }
        if name == "openai":
            return {
                "provider": "openai",
                "model": os.environ.get("OPENAI_MODEL", ""),
                "key_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
                "polish": polish,
                "note": "OpenAI-compatible endpoint. This is not the free Gemini path.",
            }
        return {
            "provider": "gemini",
            "model": os.environ.get("VISION_MODEL", GeminiVisionProvider.DEFAULT_MODEL),
            "key_configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
            "polish": polish,
            "note": "Google AI Studio free tier. The key stays on this machine.",
        }
