"""Google AI Studio Gemini. The default model is on the free tier."""

from __future__ import annotations

import base64

from listing_generator.vision.base import VisionProvider
from listing_generator.vision.errors import VisionError
from listing_generator.vision.http import JsonHttp
from listing_generator.vision.images import PreparedImage
from listing_generator.vision.json_text import ModelJson
from listing_generator.vision.prompt import VisionPrompt


class GeminiVisionProvider(VisionProvider):
    DEFAULT_MODEL = "gemini-3.5-flash"
    DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, model: str | None = None, base_url: str | None = None) -> None:
        if not api_key.strip():
            raise VisionError(
                "Set GEMINI_API_KEY to a free Google AI Studio key. "
                "Create one at https://aistudio.google.com/apikey with no credit card. "
                "Nothing is sent until a key is set."
            )
        self.api_key = api_key.strip()
        self.model = (model or GeminiVisionProvider.DEFAULT_MODEL).strip()
        self.base_url = (base_url or GeminiVisionProvider.DEFAULT_BASE).rstrip("/")
        self.name = "gemini"

    def analyze(self, images: list[PreparedImage]) -> dict:
        url, headers, payload = self.build_request(images)
        response = JsonHttp.post(url, payload, headers)
        return ModelJson.parse(ModelJson.gemini_text(response))

    def complete_text(self, prompt: str) -> str:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }
        response = JsonHttp.post(url, payload, headers)
        return ModelJson.gemini_text(response)

    def build_request(self, images: list[PreparedImage]) -> tuple[str, dict[str, str], dict]:
        parts: list[dict] = [{"text": VisionPrompt.extraction()}]
        for image in images:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": image.mime_type,
                        "data": base64.b64encode(image.data).decode("ascii"),
                    }
                }
            )
        parts.append({"text": "Return the JSON object now."})
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            },
        }
        return url, headers, payload
