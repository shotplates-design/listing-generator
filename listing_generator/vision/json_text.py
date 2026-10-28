"""Pull a JSON object out of a model response."""

from __future__ import annotations

import json

from listing_generator.vision.errors import VisionError


class ModelJson:
    @staticmethod
    def parse(text: str) -> dict:
        raw = text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VisionError("The model did not return JSON. Nothing was guessed.") from exc
        if not isinstance(parsed, dict):
            raise VisionError("The model returned JSON that was not an object. Nothing was guessed.")
        return parsed

    @staticmethod
    def gemini_text(payload: dict) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            feedback = payload.get("promptFeedback") or {}
            reason = feedback.get("blockReason") or "no candidates"
            raise VisionError(f"Gemini returned no reading ({reason}). Nothing was guessed.")
        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        texts = [part.get("text", "") for part in parts if isinstance(part, dict) and part.get("text")]
        if not texts:
            raise VisionError("Gemini returned no text. Nothing was guessed.")
        return "\n".join(texts)

    @staticmethod
    def openai_text(payload: dict) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise VisionError("The OpenAI-compatible provider returned no reading. Nothing was guessed.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            texts = [part.get("text", "") for part in content if isinstance(part, dict)]
            joined = "\n".join(text for text in texts if text)
            if joined.strip():
                return joined
        raise VisionError("The OpenAI-compatible provider returned no text. Nothing was guessed.")
