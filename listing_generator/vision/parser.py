"""Turns a model JSON object into a clothing item. Unsure readings stay blank."""

from __future__ import annotations

from listing_generator.models import ClothingItem, DiscardedReading, ExtractionResult
from listing_generator.text import Conditions, Departments, Text
from listing_generator.vision.errors import VisionError


class ExtractionParser:
    """Keeps high and medium readings. Measurements stay blank unless a ruler is visible."""

    _FIELDS = (
        "brand",
        "item_type",
        "size_tagged",
        "color",
        "material",
        "origin",
        "condition",
        "flaws",
        "style_era",
        "gender_department",
    )
    _LIMITS = {
        "brand": 60,
        "item_type": 40,
        "size_tagged": 20,
        "color": 30,
        "material": 60,
        "origin": 40,
        "style_era": 40,
        "flaws": 800,
        "gender_department": 40,
        "condition": 40,
    }
    _CONFIRM = {"condition", "flaws"}

    @staticmethod
    def parse(payload: dict, *, provider: str, model: str) -> ExtractionResult:
        if not isinstance(payload, dict):
            raise VisionError("The model response was not a JSON object. Nothing was guessed.")
        values: dict[str, str] = {}
        confidence: dict[str, str] = {}
        flags: dict[str, str] = {}
        discarded: list[DiscardedReading] = []
        for field_name in ExtractionParser._FIELDS:
            kept, level, flag, rejected = ExtractionParser._one(field_name, payload.get(field_name))
            values[field_name] = kept
            confidence[field_name] = level
            if flag:
                flags[field_name] = flag
            if rejected is not None:
                discarded.append(rejected)
        measurements, measurement_level, measurement_flag, measurement_rejected = ExtractionParser._measurements(
            payload.get("measurements")
        )
        confidence["measurements"] = measurement_level
        if measurement_flag:
            flags["measurements"] = measurement_flag
        if measurement_rejected is not None:
            discarded.append(measurement_rejected)
        item = ClothingItem(
            brand=values["brand"],
            item_type=values["item_type"],
            size_tagged=values["size_tagged"],
            color=values["color"],
            material=values["material"],
            origin=values["origin"],
            condition=values["condition"],
            flaws=values["flaws"],
            style_era=values["style_era"],
            gender_department=values["gender_department"],
            measurements=measurements,
            field_flags=flags,
            field_confidence=confidence,
            review_notes=[
                "Confirm condition, flaws, and measurements in hand. Photos hide wear, and this app will not invent them.",
            ],
        )
        return ExtractionResult(item=item, discarded=discarded, provider=provider, model=model)

    @staticmethod
    def _one(
        field_name: str, raw: object
    ) -> tuple[str, str, str, DiscardedReading | None]:
        if raw is None:
            return "", "none", "", None
        if not isinstance(raw, dict):
            shown = ExtractionParser._show(raw)
            if not shown:
                return "", "none", "Left blank. The photos did not show this.", None
            return (
                "",
                "none",
                "Left blank. The model did not say how sure it was.",
                DiscardedReading(
                    field=field_name,
                    value=shown,
                    confidence="none",
                    evidence="",
                    reason="No confidence was provided.",
                ),
            )

        confidence = str(raw.get("confidence") or "none").strip().lower()
        if confidence not in {"high", "medium", "low", "none"}:
            confidence = "none"
        evidence = Text.squash(raw.get("evidence"))[:120]
        value = ExtractionParser._clean(field_name, raw.get("value"))
        shown = ExtractionParser._show(raw.get("value"))
        if Text.is_placeholder(value):
            return (
                "",
                "none",
                "Left blank. The model did not read this.",
                DiscardedReading(
                    field=field_name,
                    value=shown,
                    confidence=confidence,
                    evidence=evidence,
                    reason="Placeholder, not a reading.",
                ),
            )
        limit = ExtractionParser._LIMITS.get(field_name)
        if value and limit and len(value) > limit:
            return (
                "",
                "none",
                "Left blank. The reading was too long to trust.",
                DiscardedReading(
                    field=field_name,
                    value=shown,
                    confidence=confidence,
                    evidence=evidence,
                    reason="Reading was too long to trust.",
                ),
            )
        if field_name == "condition" and value:
            canonical = Conditions.normalize(value)
            if not canonical:
                return (
                    "",
                    "none",
                    "Left blank. The condition reading was not a known grade.",
                    DiscardedReading(field=field_name, value=value, confidence=confidence, evidence=evidence, reason="Unrecognized condition."),
                )
            value = canonical
        if field_name == "gender_department" and value:
            canonical = Departments.normalize(value)
            if not canonical:
                return (
                    "",
                    "none",
                    "Left blank. The department reading was not explicit.",
                    DiscardedReading(field=field_name, value=value, confidence=confidence, evidence=evidence, reason="Unrecognized department."),
                )
            value = canonical
        if not value or confidence in {"low", "none"}:
            reason = "Not readable in the photos." if not value else "The model was not sure."
            rejected = None
            if shown:
                rejected = DiscardedReading(
                    field=field_name,
                    value=shown,
                    confidence=confidence,
                    evidence=evidence,
                    reason=reason,
                )
            flag = "Left blank. Not readable in the photos." if not shown else f"Left blank. {reason}"
            return "", "none", flag, rejected
        if field_name in ExtractionParser._CONFIRM:
            return value, confidence, "Kept from the photos, but confirm it in hand before posting.", None
        if confidence == "medium":
            detail = f" ({evidence})" if evidence else ""
            return value, "medium", f"Check this. The reading was uncertain{detail}.", None
        return value, "high", "", None

    @staticmethod
    def _measurements(raw: object) -> tuple[dict[str, str], str, str, DiscardedReading | None]:
        blank_flag = "Left blank. Measurements cannot be read from photos."
        shown = ExtractionParser._show(raw)
        evidence = ExtractionParser._evidence(raw)
        confidence = ExtractionParser._raw_confidence(raw).strip().lower()
        if confidence not in {"high", "medium", "low", "none"}:
            confidence = "none"
        values: dict[str, str] = {}
        payload = raw.get("value") if isinstance(raw, dict) else None
        if isinstance(payload, dict):
            for key, item in payload.items():
                text = Text.squash(item)
                if text and not Text.is_placeholder(text):
                    values[str(key)] = text
        ruler = ExtractionParser._mentions_ruler(evidence)
        if values and ruler and confidence in {"high", "medium"}:
            if isinstance(raw, dict) and raw.get("approximate") is True:
                return (
                    values,
                    "medium",
                    "Approximate. A ruler is visible, but the span is not exact. Measure again before posting.",
                    None,
                )
            return values, confidence, "", None
        rejected = None
        if shown:
            rejected = DiscardedReading(
                field="measurements",
                value=shown,
                confidence=confidence,
                evidence=evidence,
                reason="Measurements cannot be read from photos unless a ruler or tape is visible.",
            )
        return {}, "none", blank_flag, rejected

    @staticmethod
    def _mentions_ruler(evidence: str) -> bool:
        text = evidence.lower()
        return any(word in text for word in ("ruler", "tape measure", "measuring tape", "yardstick"))

    @staticmethod
    def _clean(field_name: str, value: object) -> str:
        if isinstance(value, list):
            return "\n".join(Text.squash(part) for part in value if Text.squash(part))
        if isinstance(value, dict):
            return ""
        return Text.squash(value)

    @staticmethod
    def _show(raw: object) -> str:
        if isinstance(raw, dict) and "value" in raw:
            return ExtractionParser._show(raw.get("value"))
        if isinstance(raw, dict):
            parts = [f"{key}: {ExtractionParser._show(value)}" for key, value in raw.items() if ExtractionParser._show(value)]
            return "; ".join(parts)
        if isinstance(raw, list):
            return "; ".join(ExtractionParser._show(part) for part in raw if ExtractionParser._show(part))
        return Text.squash(raw)

    @staticmethod
    def _raw_confidence(raw: object) -> str:
        if isinstance(raw, dict) and "confidence" in raw:
            return str(raw.get("confidence") or "")
        if isinstance(raw, dict) and isinstance(raw.get("value"), dict):
            return str(raw["value"].get("confidence") or "")
        return ""

    @staticmethod
    def _evidence(raw: object) -> str:
        if isinstance(raw, dict):
            if raw.get("evidence"):
                return Text.squash(raw.get("evidence"))[:120]
            value = raw.get("value")
            if isinstance(value, dict):
                return Text.squash(value.get("evidence"))[:120]
        return ""
