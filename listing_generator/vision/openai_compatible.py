"""Optional OpenAI-compatible vision endpoint. This path is usually billed by that provider."""

from __future__ import annotations

import base64

from listing_generator.vision.base import VisionProvider
from listing_generator.vision.errors import VisionError
from listing_generator.vision.http import JsonHttp
from listing_generator.vision.images import PreparedImage
from listing_generator.vision.json_text import ModelJson
from listing_generator.vision.prompt import VisionPrompt


class OpenAICompatibleVisionProvider(VisionProvider):
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1") -> None:
        if not api_key.strip():
            raise VisionError("Set OPENAI_API_KEY for the OpenAI-compatible provider. Nothing was sent.")
        if not model.strip():
            raise VisionError("Set OPENAI_MODEL to a vision-capable model id.")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.name = "openai"

    def analyze(self, images: list[PreparedImage]) -> dict:
        url, headers, payload = self.build_request(images)
        response = JsonHttp.post(url, payload, headers)
        return ModelJson.parse(ModelJson.openai_text(response))

    def complete_text(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        }
        response = JsonHttp.post(url, payload, headers)
        return ModelJson.openai_text(response)

    def build_request(self, images: list[PreparedImage]) -> tuple[str, dict[str, str], dict]:
        content: list[dict] = [{"type": "text", "text": VisionPrompt.extraction()}]
        for image in images:
            encoded = base64.b64encode(image.data).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image.mime_type};base64,{encoded}"},
                }
            )
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": content}],
        }
        return url, headers, payload
