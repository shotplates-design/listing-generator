"""Offline fixture. It is not a vision model and it does not look at the pixels."""

from __future__ import annotations

from copy import deepcopy

from PIL import Image, ImageDraw


class SampleReading:
    @staticmethod
    def payload() -> dict:
        return deepcopy(
            {
                "brand": {"value": "Nike", "confidence": "high", "evidence": "wordmark on the chest"},
                "item_type": {"value": "hoodie", "confidence": "high", "evidence": "hood and kangaroo pocket"},
                "size_tagged": {"value": "M", "confidence": "high", "evidence": "size tag reads M"},
                "color": {"value": "navy", "confidence": "high", "evidence": "garment color in the front photo"},
                "material": {
                    "value": "cotton blend",
                    "confidence": "medium",
                    "evidence": "care tag is partly folded",
                },
                "condition": {
                    "value": "good",
                    "confidence": "low",
                    "evidence": "cannot grade wear from these photos",
                },
                "flaws": {
                    "value": "Small hole near the left hem",
                    "confidence": "high",
                    "evidence": "visible in the flaw photo",
                },
                "style_era": {"value": "90s athletic", "confidence": "medium", "evidence": "logo scale and cut"},
                "gender_department": {
                    "value": "womens",
                    "confidence": "low",
                    "evidence": "cut is not decisive",
                },
                "measurements": {
                    "value": {"pit_to_pit": "22 in", "length": "27 in"},
                    "confidence": "high",
                    "evidence": "estimated from the hanger photo",
                },
            }
        )


class SamplePhotos:
    """Generated cards so the offline provider has something to upload. They are not a reading."""

    @staticmethod
    def build() -> list[tuple[str, bytes]]:
        cards = (
            ("sample-front.png", (22, 48, 84), "FRONT", "navy hoodie"),
            ("sample-back.png", (18, 36, 64), "BACK", "plain back"),
            ("sample-tag.png", (244, 240, 230), "TAG", "NIKE  M"),
            ("sample-flaw.png", (90, 28, 36), "FLAW", "hole at hem"),
        )
        return [(name, SamplePhotos._png(color, title, subtitle)) for name, color, title, subtitle in cards]

    @staticmethod
    def _png(color: tuple[int, int, int], title: str, subtitle: str) -> bytes:
        from io import BytesIO

        image = Image.new("RGB", (640, 800), color)
        draw = ImageDraw.Draw(image)
        ink = (248, 244, 236) if sum(color) < 380 else (28, 25, 21)
        draw.rounded_rectangle((70, 80, 570, 720), radius=28, outline=ink, width=4)
        draw.text((90, 140), title, fill=ink)
        draw.text((90, 200), subtitle, fill=ink)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
