"""Hashtags, style tags, keywords, and eBay item specifics."""

from __future__ import annotations

from listing_generator.fees import FeeSchedule
from listing_generator.models import ClothingItem
from listing_generator.text import Conditions, Departments, Text


class TagBuilder:
    """Search tags from confirmed fields. Empty fields are skipped."""

    @staticmethod
    def depop(item: ClothingItem, config: dict | None = None) -> tuple[str, ...]:
        schedule = config or FeeSchedule.load()
        limit = int(schedule["depop_hashtag_limit"])
        seeds: list[str] = []
        if item.brand:
            seeds.append(item.brand)
        if item.item_type:
            seeds.append(item.item_type)
        if item.color:
            seeds.append(item.color)
        if item.gender_department:
            seeds.append(item.gender_department)
        for word in Text.squash(item.style_era).split(" "):
            seeds.append(word)
        tags: list[str] = []
        for seed in seeds:
            tag = Text.hashtag(seed)
            if tag and tag not in tags:
                tags.append(tag)
            if len(tags) == limit:
                break
        return tuple(tags)

    @staticmethod
    def poshmark(item: ClothingItem, config: dict | None = None) -> tuple[str, ...]:
        schedule = config or FeeSchedule.load()
        limit = int(schedule["poshmark_style_tag_limit"])
        seeds = [Text.label(item.brand), Text.label(item.item_type), Text.label(item.style_era)]
        tags: list[str] = []
        for seed in seeds:
            if seed and seed not in tags:
                tags.append(seed)
            if len(tags) == limit:
                break
        return tuple(tags)

    @staticmethod
    def mercari(item: ClothingItem, config: dict | None = None) -> tuple[str, ...]:
        schedule = config or FeeSchedule.load()
        limit = int(schedule["mercari_keyword_limit"])
        seeds = [
            Text.label(item.brand),
            Text.label(item.item_type),
            Text.label(item.color),
            Text.squash(item.size_tagged),
            Text.label(item.material),
        ]
        tags: list[str] = []
        for seed in seeds:
            if seed and seed not in tags:
                tags.append(seed)
            if len(tags) == limit:
                break
        return tuple(tags)

    @staticmethod
    def whatnot(item: ClothingItem) -> tuple[str, ...]:
        rows = []
        if item.brand:
            rows.append(f"Brand: {Text.label(item.brand)}")
        if item.item_type:
            rows.append(f"Type: {Text.label(item.item_type)}")
        if item.size_tagged:
            rows.append(f"Size: {Text.squash(item.size_tagged)}")
        if item.color:
            rows.append(f"Color: {Text.label(item.color)}")
        if item.gender_department:
            rows.append(f"Department: {Departments.display(item.gender_department)}")
        return tuple(rows)


class ItemSpecifics:
    """eBay item specifics. A blank fact is listed as missing, not filled in."""

    _ROWS = (
        ("brand", "Brand"),
        ("item_type", "Type"),
        ("gender_department", "Department"),
        ("size_tagged", "Size"),
        ("color", "Color"),
        ("material", "Material"),
        ("style_era", "Style"),
        ("condition", "Condition"),
    )

    @staticmethod
    def ebay(item: ClothingItem) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
        present: list[tuple[str, str]] = []
        missing: list[str] = []
        for field_name, label in ItemSpecifics._ROWS:
            raw = getattr(item, field_name)
            if field_name == "gender_department":
                value = Departments.display(raw)
            elif field_name == "condition":
                value = Conditions.platform_label(raw, "ebay")
            elif field_name == "size_tagged":
                value = Text.squash(raw)
            else:
                value = Text.label(raw) if field_name != "brand" else Text.label(raw)
            if value:
                present.append((label, value))
            else:
                missing.append(label)
        return tuple(present), tuple(missing)

    @staticmethod
    def facebook(item: ClothingItem) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
        label = Conditions.platform_label(item.condition, "facebook_marketplace")
        if label:
            return (("Condition", label),), ()
        return (), ("Condition",)
