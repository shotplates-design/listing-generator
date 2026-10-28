"""Turns uploads into JPEG payloads small enough for one free-tier request."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from listing_generator.vision.errors import VisionError


@dataclass(frozen=True)
class PreparedImage:
    filename: str
    data: bytes
    mime_type: str


class ImagePrep:
    MAX_IMAGES = 8
    MAX_EDGE = 2048
    MAX_SOURCE_BYTES = 15 * 1024 * 1024

    @staticmethod
    def prepare_many(files: list[tuple[str, bytes]]) -> list[PreparedImage]:
        if not files:
            raise VisionError("Add at least one photo.")
        if len(files) > ImagePrep.MAX_IMAGES:
            raise VisionError(
                f"Use at most {ImagePrep.MAX_IMAGES} photos: front, back, tag, and flaws. "
                "That keeps one free-tier request small."
            )
        return [ImagePrep.prepare(name, data) for name, data in files]

    @staticmethod
    def prepare(filename: str, data: bytes) -> PreparedImage:
        if len(data) > ImagePrep.MAX_SOURCE_BYTES:
            raise VisionError(f"{filename} is over 15 MB. Export a smaller JPEG and try again.")
        try:
            image = Image.open(BytesIO(data))
            image.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise VisionError(f"{filename} is not a JPEG, PNG, or WebP photo.") from exc
        if getattr(image, "is_animated", False):
            image.seek(0)
        if image.mode in ("RGBA", "LA"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        image.thumbnail((ImagePrep.MAX_EDGE, ImagePrep.MAX_EDGE))
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85, optimize=True)
        return PreparedImage(filename=filename or "photo.jpg", data=buffer.getvalue(), mime_type="image/jpeg")
