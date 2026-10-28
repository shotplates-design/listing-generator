"""Platform titles. Each one is cut to the limit in the fee config."""

from __future__ import annotations

from listing_generator.fees import FeeSchedule
from listing_generator.models import ClothingItem
from listing_generator.text import Conditions, Departments, Text


class TitleBuilder:
    """Builds one title per platform from confirmed fields only."""

    @staticmethod
    def limit(platform: str, config: dict | None = None) -> int:
        schedule = config or FeeSchedule.load()
        return int(schedule["title_limits"][platform])

    @staticmethod
    def fit(parts: list[str], limit: int, separator: str = " ") -> str:
        cleaned = Text.dedupe([Text.squash(part) for part in parts if Text.squash(part)])
        if not cleaned:
            return "Clothing"[:limit]
        while len(cleaned) > 1 and len(separator.join(cleaned)) > limit:
            cleaned.pop()
        title = separator.join(cleaned)
        if len(title) > limit:
            title = title[:limit].rstrip()
        title = title.rstrip(" ·,—-|")
        if not title:
            return "Clothing"[:limit]
        return title

    @staticmethod
    def size_phrase(size: str) -> str:
        text = Text.squash(size)
        if not text:
            return ""
        if text.lower().startswith("size "):
            return Text.label(text)
        return f"Size {text}"

    @staticmethod
    def ebay(item: ClothingItem, config: dict | None = None) -> str:
        limit = TitleBuilder.limit("ebay", config)
        parts = [
            Text.label(item.brand),
            Text.label(item.item_type),
            Departments.display(item.gender_department),
            TitleBuilder.size_phrase(item.size_tagged),
            Text.label(item.color),
            Text.label(item.material),
            Text.label(item.style_era),
            Conditions.title_token(item.condition),
        ]
        return TitleBuilder.fit(parts, limit)

    @staticmethod
    def poshmark(item: ClothingItem, config: dict | None = None) -> str:
        limit = TitleBuilder.limit("poshmark", config)
        condition = Conditions.title_token(item.condition)
        token = condition if condition in {"NWT", "NWOT"} else ""
        parts = [
            Text.label(item.brand),
            Text.label(item.item_type),
            Departments.display(item.gender_department),
            TitleBuilder.size_phrase(item.size_tagged),
            Text.label(item.color),
            Text.label(item.material),
            Text.label(item.style_era),
            token,
        ]
        return TitleBuilder.fit(parts, limit)

    @staticmethod
    def mercari(item: ClothingItem, config: dict | None = None) -> str:
        limit = TitleBuilder.limit("mercari", config)
        condition = Conditions.title_token(item.condition)
        token = condition if condition in {"NWT", "NWOT"} else ""
        parts = [
            Text.label(item.brand),
            Text.label(item.item_type),
            Departments.display(item.gender_department),
            TitleBuilder.size_phrase(item.size_tagged),
            Text.label(item.color),
            Text.label(item.material),
            token,
        ]
        return TitleBuilder.fit(parts, limit)

    @staticmethod
    def depop(item: ClothingItem, config: dict | None = None) -> str:
        """Casual opening line. Hashtags stay in the description, not here."""
        limit = TitleBuilder.limit("depop", config)
        bits = [
            item.color.lower(),
            item.material.lower(),
            item.brand.lower(),
            item.item_type.lower(),
        ]
        sentence = " ".join(Text.squash(bit) for bit in bits if Text.squash(bit))
        extras = []
        adjective = Departments.adjective(item.gender_department)
        if adjective:
            extras.append(adjective)
        if Text.squash(item.size_tagged):
            extras.append(f"size {Text.squash(item.size_tagged).lower()}")
        if extras:
            tail = ", ".join(extras)
            sentence = f"{sentence}, {tail}" if sentence else tail
        style = Text.squash(item.style_era).lower()
        if style:
            candidate = f"{sentence} — {style}" if sentence else style
            if len(candidate) <= limit:
                sentence = candidate
        if not sentence:
            sentence = "clothing"
        return TitleBuilder.fit([sentence], limit)

    @staticmethod
    def whatnot(item: ClothingItem, config: dict | None = None) -> str:
        """Short show-card title. The cap is this app's, so it fits a live tile."""
        limit = TitleBuilder.limit("whatnot", config)
        size = Text.squash(item.size_tagged)
        parts = [
            Text.label(item.brand),
            Text.label(item.item_type),
            size,
            Text.label(item.color),
        ]
        return TitleBuilder.fit(parts, limit, separator=" · ")

    @staticmethod
    def facebook(item: ClothingItem, config: dict | None = None) -> str:
        """Short plain title. The cap is about 100 characters, with no hashtags."""
        limit = TitleBuilder.limit("facebook_marketplace", config)
        parts = [
            Text.label(item.brand),
            Departments.display(item.gender_department),
            Text.label(item.item_type),
            TitleBuilder.size_phrase(item.size_tagged),
            Text.label(item.color),
        ]
        return TitleBuilder.fit(parts, limit)

    @staticmethod
    def for_platform(platform: str, item: ClothingItem, config: dict | None = None) -> str:
        builders = {
            "ebay": TitleBuilder.ebay,
            "poshmark": TitleBuilder.poshmark,
            "mercari": TitleBuilder.mercari,
            "depop": TitleBuilder.depop,
            "whatnot": TitleBuilder.whatnot,
            "facebook_marketplace": TitleBuilder.facebook,
        }
        title = builders[platform](item, config)
        limit = TitleBuilder.limit(platform, config)
        if len(title) > limit:
            title = TitleBuilder.fit([title], limit)
        return title
