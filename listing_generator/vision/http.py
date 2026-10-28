"""JSON POST used by the vision providers. API keys stay in headers, never in the URL."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from listing_generator.vision.errors import VisionError


class JsonHttp:
    @staticmethod
    def post(url: str, payload: dict, headers: dict[str, str], timeout: float = 90) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            message = JsonHttp.scrub(f"Vision request failed ({exc.code}). {detail}")
            if exc.code == 429 or "quota" in detail.lower() or "resource_exhausted" in detail.lower():
                message = (
                    "The vision provider refused the request because the quota is used up. "
                    "On Gemini's free tier, daily limits reset at midnight Pacific. "
                    "Check the caps in Google AI Studio. Nothing was guessed."
                )
            raise VisionError(message) from exc
        except urllib.error.URLError as exc:
            raise VisionError(JsonHttp.scrub(f"Could not reach the vision provider. {exc.reason}")) from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VisionError("The vision provider returned a response that was not JSON.") from exc
        if not isinstance(parsed, dict):
            raise VisionError("The vision provider returned a response that was not a JSON object.")
        return parsed

    @staticmethod
    def scrub(text: str) -> str:
        cleaned = text
        for name in ("GEMINI_API_KEY", "OPENAI_API_KEY"):
            secret = os.environ.get(name, "")
            if secret:
                cleaned = cleaned.replace(secret, "[redacted]")
        return cleaned
