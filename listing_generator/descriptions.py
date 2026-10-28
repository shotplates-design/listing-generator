"""Buyer-facing descriptions. Unknown facts are omitted, not invented."""

from __future__ import annotations

from listing_generator.fees import FeeSchedule
from listing_generator.models import ClothingItem, Fields
from listing_generator.tags import TagBuilder
from listing_generator.text import Conditions, Departments, Text
from listing_generator.titles import TitleBuilder


class DescriptionBuilder:
    """Writes the description, including a measurements block and condition notes."""

    @staticmethod
    def limit(platform: str, config: dict | None = None) -> int:
        schedule = config or FeeSchedule.load()
        return int(schedule["description_limits"][platform])

    @staticmethod
    def build(item: ClothingItem, platform: str, config: dict | None = None) -> str:
        if platform == "depop":
            opener = TitleBuilder.depop(item, config)
        else:
            opener = DescriptionBuilder._opener(item, platform)
        sections = [
            opener,
            DescriptionBuilder._details(item),
            DescriptionBuilder._measurements(item),
            DescriptionBuilder._condition(item, platform),
            "Photos are of the actual item.",
        ]
        body = "\n\n".join(section for section in sections if section)
        if platform == "depop":
            tags = " ".join(TagBuilder.depop(item, config))
            if tags:
                candidate = f"{body}\n\n{tags}"
                if len(candidate) <= DescriptionBuilder.limit(platform, config):
                    body = candidate
                else:
                    room = DescriptionBuilder.limit(platform, config) - len(body) - 2
                    kept: list[str] = []
                    for tag in tags.split(" "):
                        trial = " ".join(kept + [tag])
                        if len(trial) <= room:
                            kept.append(tag)
                        else:
                            break
                    if kept:
                        body = f"{body}\n\n{' '.join(kept)}"
        return DescriptionBuilder._cap(body, DescriptionBuilder.limit(platform, config))

    @staticmethod
    def _opener(item: ClothingItem, platform: str) -> str:
        subject: list[str] = []
        if item.brand:
            subject.append(Text.label(item.brand))
        adjective = Departments.adjective(item.gender_department)
        if adjective:
            subject.append(adjective)
        if item.item_type:
            subject.append(Text.squash(item.item_type).lower())
        if not subject and not item.color and not item.size_tagged:
            return ""
        sentence = " ".join(subject)
        tail: list[str] = []
        if item.color:
            tail.append(f"in {Text.squash(item.color).lower()}")
        if item.size_tagged:
            tail.append(f"size {Text.squash(item.size_tagged)}")
        if sentence and tail:
            sentence = f"{sentence} {', '.join(tail)}"
        elif tail:
            sentence = " ".join(tail)
        sentence = sentence[:1].upper() + sentence[1:] if sentence else sentence
        if platform == "whatnot" and sentence:
            return sentence + "."
        extras = []
        if item.material:
            extras.append(Text.label(item.material) + ".")
        if item.style_era:
            extras.append(Text.label(item.style_era) + ".")
        main = f"{sentence}." if sentence else ""
        return " ".join(part for part in (main, *extras) if part)

    @staticmethod
    def _details(item: ClothingItem) -> str:
        rows = []
        pairs = (
            ("Brand", Text.label(item.brand)),
            ("Size on tag", Text.squash(item.size_tagged)),
            ("Color", Text.label(item.color)),
            ("Material", Text.label(item.material)),
            ("Origin", Text.label(item.origin)),
            ("Department", Departments.display(item.gender_department)),
            ("Style", Text.label(item.style_era)),
        )
        for label, value in pairs:
            if value:
                rows.append(f"{label}: {value}")
        if not rows:
            return ""
        return "Details\n" + "\n".join(rows)

    @staticmethod
    def _measurements(item: ClothingItem) -> str:
        rows = []
        for key, label in Fields.MEASUREMENTS:
            value = Text.squash(item.measurements.get(key, ""))
            if value:
                rows.append(f"{label}: {value}")
        if not rows:
            return "Measurements\nNot included."
        if "approximate" in item.field_flags.get("measurements", "").lower():
            rows.append("Approximate, from a ruler in the photos. Measure the garment again before posting.")
        return "Measurements\n" + "\n".join(rows)

    @staticmethod
    def _condition(item: ClothingItem, platform: str) -> str:
        label = Conditions.platform_label(item.condition, platform)
        flaw = Text.squash(item.flaws)
        poor_note = ""
        if platform == "facebook_marketplace" and item.condition == "poor" and label:
            poor_note = "Seller grade is Poor. Facebook's lowest condition is Used - Fair."
        if label and flaw and poor_note:
            return f"Condition\n{label}. {flaw}. {poor_note}"
        if label and poor_note:
            return f"Condition\n{label}. {poor_note}"
        if label and flaw:
            return f"Condition\n{label}. {flaw}."
        if label:
            return f"Condition\n{label}."
        if flaw:
            return f"Condition\nNoted flaw: {flaw}."
        return ""

    @staticmethod
    def _cap(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        trimmed = text[: limit - 1].rstrip()
        return trimmed + "…"
