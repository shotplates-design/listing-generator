"""Command line. `generate --format json` prints the v1 export and nothing is posted."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from listing_generator.export import ExportError, ListingExport
from listing_generator.generator import ListingGenerator
from listing_generator.models import ClothingItem, PhotoRef, PhotoRoles
from listing_generator.money import MoneyError
from listing_generator.vision.errors import VisionError
from listing_generator.vision.factory import VisionProviders
from listing_generator.vision.images import ImagePrep
from listing_generator.vision.parser import ExtractionParser


class CommandLine:
    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="listing-generator",
            description="Read clothing photos and draft resale listings. Nothing is posted.",
        )
        sub = parser.add_subparsers(dest="command", required=True)

        analyze = sub.add_parser("analyze", help="Read photos and write a review file.")
        analyze.add_argument("photos", nargs="+", help="JPEG, PNG, or WebP photos.")
        analyze.add_argument("--role", action="append", default=[], help="Role for each photo, in order: front, back, tag, flaw, or detail.")
        analyze.add_argument("--output", "-o", help="Where to write the review JSON. Defaults to stdout.")
        analyze.add_argument("--provider", choices=("gemini", "openai", "mock"), help="Overrides VISION_PROVIDER for this run.")

        generate = sub.add_parser("generate", help="Draft listings and write the v1 export.")
        generate.add_argument("item", help="Review JSON from analyze, or a v1 export to rebuild.")
        generate.add_argument("--format", choices=("text", "json", "csv"), default="text")
        generate.add_argument("--output", "-o", help="Where to write. Defaults to stdout.")
        generate.add_argument("--item-id", help="Stable id for the v1 document.")

        args = parser.parse_args(argv)
        try:
            if args.command == "analyze":
                return CommandLine._analyze(args)
            return CommandLine._generate(args)
        except (VisionError, ExportError, MoneyError, OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    @staticmethod
    def _analyze(args: argparse.Namespace) -> int:
        if args.provider:
            import os

            os.environ["VISION_PROVIDER"] = args.provider
        files = []
        photos: list[PhotoRef] = []
        for index, raw_path in enumerate(args.photos):
            path = Path(raw_path)
            data = path.read_bytes()
            files.append((path.name, data))
            role = args.role[index] if index < len(args.role) else PhotoRoles.default_for_index(index)
            photos.append(PhotoRef(path_or_url=str(path), role=PhotoRoles.normalize(role), order=index))
        prepared = ImagePrep.prepare_many(files)
        provider = VisionProviders.from_env()
        result = ExtractionParser.parse(
            provider.analyze(prepared),
            provider=provider.name,
            model=provider.model,
            photo_count=len(prepared),
        )
        document = {
            "provider": result.provider,
            "model": result.model,
            "item": result.item.to_dict(),
            "photos": [
                {"path_or_url": photo.path_or_url, "role": photo.role, "order": photo.order} for photo in photos
            ],
            "discarded": [
                {
                    "field": row.field,
                    "value": row.value,
                    "confidence": row.confidence,
                    "evidence": row.evidence,
                    "reason": row.reason,
                }
                for row in result.discarded
            ],
        }
        CommandLine._write(json.dumps(document, indent=2) + "\n", args.output)
        print(
            f"Read {len(photos)} photo(s) with {result.provider}. Blank fields were left blank.",
            file=sys.stderr,
        )
        return 0

    @staticmethod
    def _generate(args: argparse.Namespace) -> int:
        payload = json.loads(Path(args.item).read_text(encoding="utf-8"))
        item, photos, discarded = CommandLine._load(payload)
        listings = ListingGenerator.generate(item)
        document = ListingExport.build(
            item,
            listings,
            photos,
            discarded=discarded,
            item_id=args.item_id,
        )
        if args.format == "json":
            rendered = ListingExport.dumps(document)
        elif args.format == "csv":
            rendered = ListingExport.to_csv(document)
        else:
            rendered = CommandLine._text(document)
        CommandLine._write(rendered, args.output)
        return 0

    @staticmethod
    def _load(payload: dict) -> tuple[ClothingItem, tuple[PhotoRef, ...], tuple]:
        from listing_generator.models import DiscardedReading

        if payload.get("schema_version"):
            return ListingExport.item_from_document(payload)
        item = ClothingItem.from_dict(payload.get("item") or payload)
        photo_rows = payload.get("photos") or []
        photos = tuple(
            PhotoRef(
                path_or_url=str(row.get("path_or_url") or row.get("path") or ""),
                role=PhotoRoles.normalize(str(row.get("role") or "detail")),
                order=int(row.get("order", index)),
            )
            for index, row in enumerate(photo_rows)
            if isinstance(row, dict)
        )
        discarded = tuple(
            DiscardedReading(
                field=str(row.get("field") or ""),
                value=str(row.get("value") or ""),
                confidence=str(row.get("confidence") or ""),
                evidence=str(row.get("evidence") or ""),
                reason=str(row.get("reason") or ""),
            )
            for row in payload.get("discarded") or []
            if isinstance(row, dict)
        )
        return item, photos, discarded

    @staticmethod
    def _text(document: dict) -> str:
        lines = [
            f"schema {document['schema_version']}  item {document['item_id']}",
            f"fee schedule as of {document['fee_schedule_as_of']}",
            "",
        ]
        attributes = document["attributes"]
        lines.append(
            "Item: "
            + ", ".join(
                part
                for part in (
                    attributes["brand"],
                    attributes["category"],
                    attributes["size_tag"],
                    attributes["color"],
                )
                if part
            )
        )
        if document["field_flags"]:
            lines.append("Flags: " + "; ".join(f"{name}: {message}" for name, message in document["field_flags"].items()))
        lines.append("")
        for platform, listing in document["listings"].items():
            lines.append(f"{listing['display_name']} ({platform})")
            lines.append(f"Title ({len(listing['title'])}/{listing['title_limit']}): {listing['title']}")
            lines.append(f"Category: {listing['category_suggestion']}")
            price = listing["price"] or "not set"
            net = listing["net"] or "n/a"
            fee_total = "n/a" if listing["fees"] is None else listing["fees"]["total"]
            lines.append(f"Price: {price}    Fee: {fee_total}    Net: {net}")
            if listing["fees"] is not None:
                lines.append(listing["fees"]["formula"])
            lines.append(listing["price_rationale"])
            if listing["equalized_note"]:
                lines.append(listing["equalized_note"])
            if listing["tags"]:
                lines.append(f"{listing['tags_label']}: {', '.join(listing['tags'])}")
            lines.append(listing["description"])
            lines.append("")
        lines.append("Draft only. Nothing was posted.")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _write(text: str, output: str | None) -> None:
        if output:
            Path(output).write_text(text, encoding="utf-8")
            print(f"Wrote {output}", file=sys.stderr)
            return
        sys.stdout.write(text)
