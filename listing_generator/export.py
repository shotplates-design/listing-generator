"""Versioned JSON export. Every document is checked against schema/listing.v1.schema.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import jsonschema
from jsonschema import Draft202012Validator

from listing_generator.fees import FeeSchedule
from listing_generator.generator import ListingGenerator
from listing_generator.models import ClothingItem, DiscardedReading, PhotoRef, PlatformListing, Platforms
from listing_generator.money import Money

_CONFIDENCE = {"high", "medium", "low", "none", "user"}

_TO_EXPORT = {
    "brand": "brand",
    "item_type": "category",
    "size_tagged": "size_tag",
    "measurements": "measurements",
    "color": "color",
    "material": "material",
    "condition": "condition",
    "flaws": "flaws",
    "style_era": "style",
    "gender_department": "department",
}

_FROM_EXPORT = {export: internal for internal, export in _TO_EXPORT.items()}


class ExportError(ValueError):
    """The document does not match listing.v1."""


class ListingExport:
    """Builds the handoff a crosslisting app imports as-is."""

    SCHEMA_VERSION = "1.0.0"

    @staticmethod
    def schema_path() -> Path:
        return Path(__file__).resolve().parents[1] / "schema" / "listing.v1.schema.json"

    @staticmethod
    def load_schema() -> dict:
        with ListingExport.schema_path().open(encoding="utf-8") as handle:
            schema = json.load(handle)
        if schema.get("properties", {}).get("schema_version", {}).get("const") != ListingExport.SCHEMA_VERSION:
            raise ExportError("schema_version in the JSON Schema does not match ListingExport.SCHEMA_VERSION.")
        return schema

    @staticmethod
    def validate(document: dict) -> None:
        schema = ListingExport.load_schema()
        validator = Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        if not errors:
            return
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "(root)"
        raise ExportError(f"Export does not match {ListingExport.schema_path().name} at {location}: {first.message}")

    @staticmethod
    def build(
        item: ClothingItem,
        listings: tuple[PlatformListing, ...],
        photos: list[PhotoRef] | tuple[PhotoRef, ...] = (),
        *,
        discarded: list[DiscardedReading] | tuple[DiscardedReading, ...] = (),
        item_id: str | None = None,
        created_at: datetime | str | None = None,
        config: dict | None = None,
    ) -> dict:
        schedule = config or FeeSchedule.load()
        prepared = ListingGenerator.prepare(item)
        by_platform = {listing.platform: listing for listing in listings}
        missing = [platform for platform in Platforms.ORDER if platform not in by_platform]
        if missing:
            raise ExportError(f"Export is missing listings for {', '.join(missing)}.")
        document = {
            "schema_version": ListingExport.SCHEMA_VERSION,
            "item_id": item_id or str(uuid4()),
            "created_at": ListingExport._created_at(created_at),
            "fee_schedule_as_of": str(schedule["as_of"]),
            "photos": ListingExport._photos(photos),
            "attributes": ListingExport._attributes(prepared),
            "field_confidence": ListingExport._confidence(prepared),
            "field_flags": ListingExport._flags(prepared),
            "discarded": [ListingExport._discarded(row) for row in discarded],
            "review_notes": [note for note in prepared.review_notes if note.strip()],
            "pricing_inputs": {
                "cost_basis": ListingExport._money(prepared.cost_basis),
                "target_price": ListingExport._money(prepared.target_price),
                "buyer_paid_shipping": ListingExport._money(prepared.buyer_paid_shipping),
                "sales_tax": ListingExport._money(prepared.sales_tax),
                "facebook_fulfillment": prepared.facebook_fulfillment,
            },
            "listings": {platform: ListingExport._listing(by_platform[platform]) for platform in Platforms.ORDER},
        }
        ListingExport.validate(document)
        return document

    @staticmethod
    def dumps(document: dict) -> str:
        ListingExport.validate(document)
        return json.dumps(document, indent=2, ensure_ascii=False) + "\n"

    @staticmethod
    def to_csv(document: dict) -> str:
        """Spreadsheet view of a document that already matches the schema."""
        import csv
        import io

        ListingExport.validate(document)
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "item_id",
                "platform",
                "title",
                "description",
                "category_suggestion",
                "tags",
                "price",
                "fee_total",
                "net",
                "formula",
                "price_rationale",
            ],
        )
        writer.writeheader()
        for platform in Platforms.ORDER:
            listing = document["listings"][platform]
            fees = listing["fees"]
            writer.writerow(
                {
                    "item_id": document["item_id"],
                    "platform": platform,
                    "title": listing["title"],
                    "description": listing["description"],
                    "category_suggestion": listing["category_suggestion"],
                    "tags": " | ".join(listing["tags"]),
                    "price": listing["price"] or "",
                    "fee_total": "" if fees is None else fees["total"],
                    "net": listing["net"] or "",
                    "formula": "" if fees is None else fees["formula"],
                    "price_rationale": listing["price_rationale"],
                }
            )
        return buffer.getvalue()

    @staticmethod
    def item_from_document(document: dict) -> tuple[ClothingItem, tuple[PhotoRef, ...], tuple[DiscardedReading, ...]]:
        """Read a v1 document back into the facts that produced it."""
        ListingExport.validate(document)
        attributes = document["attributes"]
        confidence = {
            _FROM_EXPORT[name]: value for name, value in document["field_confidence"].items()
        }
        flags = {_FROM_EXPORT[name]: value for name, value in document["field_flags"].items()}
        prices = document["pricing_inputs"]
        item = ClothingItem(
            brand=attributes["brand"],
            item_type=attributes["category"],
            size_tagged=attributes["size_tag"],
            color=attributes["color"],
            material=attributes["material"],
            condition=attributes["condition"],
            flaws="\n".join(attributes["flaws"]),
            style_era=attributes["style"],
            gender_department=attributes["department"],
            measurements=dict(attributes["measurements"]),
            cost_basis=Money.parse(prices["cost_basis"]),
            target_price=Money.parse(prices["target_price"]),
            buyer_paid_shipping=Money.parse(prices["buyer_paid_shipping"]),
            sales_tax=Money.parse(prices["sales_tax"]),
            facebook_fulfillment=prices["facebook_fulfillment"],
            field_flags=flags,
            field_confidence=confidence,
            review_notes=list(document["review_notes"]),
        )
        photos = tuple(
            PhotoRef(path_or_url=photo["path_or_url"], role=photo["role"], order=photo["order"])
            for photo in document["photos"]
        )
        discarded = tuple(
            DiscardedReading(
                field=_FROM_EXPORT[row["field"]],
                value=row["value"],
                confidence=row["confidence"],
                evidence=row["evidence"],
                reason=row["reason"],
            )
            for row in document["discarded"]
        )
        return item, photos, discarded

    @staticmethod
    def _attributes(item: ClothingItem) -> dict:
        flaws = [line.strip() for line in item.flaws.splitlines() if line.strip()]
        return {
            "brand": item.brand,
            "category": item.item_type,
            "size_tag": item.size_tagged,
            "measurements": {key: value for key, value in item.measurements.items() if value.strip()},
            "color": item.color,
            "material": item.material,
            "condition": item.condition,
            "flaws": flaws,
            "style": item.style_era,
            "department": item.gender_department,
        }

    @staticmethod
    def _confidence(item: ClothingItem) -> dict:
        attributes = ListingExport._attributes(item)
        output = {}
        for internal, export_name in _TO_EXPORT.items():
            recorded = item.field_confidence.get(internal, "")
            value = attributes[export_name]
            filled = bool(value) if not isinstance(value, (dict, list)) else bool(value)
            if recorded in _CONFIDENCE and not (recorded == "none" and filled):
                output[export_name] = recorded
                continue
            output[export_name] = "user" if filled else "none"
        return output

    @staticmethod
    def _flags(item: ClothingItem) -> dict:
        flags = {}
        for internal, message in item.field_flags.items():
            export_name = _TO_EXPORT.get(internal)
            if export_name and message.strip():
                flags[export_name] = message.strip()
        return flags

    @staticmethod
    def _discarded(row: DiscardedReading) -> dict:
        field_name = _TO_EXPORT.get(row.field, row.field)
        if field_name not in _FROM_EXPORT:
            raise ExportError(f"Discarded field {row.field!r} is not in the v1 contract.")
        return {
            "field": field_name,
            "value": row.value,
            "confidence": row.confidence,
            "evidence": row.evidence,
            "reason": row.reason,
        }

    @staticmethod
    def _photos(photos: list[PhotoRef] | tuple[PhotoRef, ...]) -> list[dict]:
        from listing_generator.models import PhotoRoles

        ordered = sorted(photos, key=lambda photo: (photo.order, photo.path_or_url))
        cleaned = []
        for photo in ordered:
            path = photo.path_or_url.strip()
            if not path:
                raise ExportError("Each photo needs a path or URL.")
            row = {"path_or_url": path, "role": photo.role, "order": photo.order}
            role = row["role"]
            if role not in PhotoRoles.CHOICES:
                raise ExportError(f"Photo role {role!r} is not one of {', '.join(PhotoRoles.CHOICES)}.")
            if row["order"] < 0:
                raise ExportError("Photo order cannot be negative.")
            cleaned.append({"path_or_url": row["path_or_url"], "role": role, "order": row["order"]})
        return cleaned

    @staticmethod
    def _listing(listing: PlatformListing) -> dict:
        fee = listing.fee
        fees = None
        if fee is not None:
            fees = {
                "currency": "USD",
                "fee_base": ListingExport._required_money(fee.fee_base),
                "total": ListingExport._required_money(fee.total_fee),
                "formula": fee.formula,
                "lines": [
                    {"label": line.label, "amount": ListingExport._required_money(line.amount)}
                    for line in fee.lines
                ],
                "notes": list(fee.notes),
            }
        return {
            "display_name": listing.display_name,
            "title": listing.title,
            "title_limit": listing.title_limit,
            "description": listing.description,
            "description_limit": listing.description_limit,
            "tags": list(listing.tags),
            "tags_label": listing.tags_label,
            "category_suggestion": listing.category,
            "category_note": listing.category_note,
            "item_specifics": {key: value for key, value in listing.item_specifics},
            "missing_specifics": list(listing.missing_specifics),
            "price": ListingExport._money(listing.list_price),
            "price_rationale": listing.price_rationale,
            "equalized_price": ListingExport._money(listing.equalized_list_price),
            "equalized_note": listing.equalized_note,
            "fees": fees,
            "net": None if fee is None else ListingExport._required_money(fee.net),
            "checklist": list(listing.checklist),
            "polish": listing.polish,
        }

    @staticmethod
    def _money(value: Decimal | None) -> str | None:
        if value is None:
            return None
        return f"{Money.quantize(value):.2f}"

    @staticmethod
    def _required_money(value: Decimal) -> str:
        return f"{Money.quantize(value):.2f}"

    @staticmethod
    def _created_at(value: datetime | str | None) -> str:
        if value is None:
            moment = datetime.now(timezone.utc)
        elif isinstance(value, str):
            return value
        else:
            moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            moment = moment.astimezone(timezone.utc)
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
