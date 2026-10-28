"""Optional wording pass. Off unless LISTING_LLM_POLISH=1. Titles are cut back to the limit afterward."""

from __future__ import annotations

import json
import os
from dataclasses import replace

from listing_generator.descriptions import DescriptionBuilder
from listing_generator.models import PlatformListing
from listing_generator.titles import TitleBuilder
from listing_generator.vision.json_text import ModelJson


class ListingPolish:
    @staticmethod
    def enabled() -> bool:
        return os.environ.get("LISTING_LLM_POLISH", "0").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def apply(
        listings: tuple[PlatformListing, ...],
        completer=None,
    ) -> tuple[PlatformListing, ...]:
        if not ListingPolish.enabled():
            return listings
        if completer is None:
            from listing_generator.vision.factory import VisionProviders

            completer = VisionProviders.from_env().complete_text
        draft = {
            listing.platform: {
                "title_limit": listing.title_limit,
                "title": listing.title,
                "description": listing.description,
            }
            for listing in listings
        }
        try:
            parsed = ModelJson.parse(completer(json.dumps(draft)))
        except Exception:
            return tuple(replace(listing, polish="fallback") for listing in listings)
        updated: list[PlatformListing] = []
        for listing in listings:
            raw = parsed.get(listing.platform)
            if not isinstance(raw, dict):
                updated.append(replace(listing, polish="fallback"))
                continue
            title = raw.get("title") if isinstance(raw.get("title"), str) and raw.get("title").strip() else listing.title
            description = (
                raw.get("description")
                if isinstance(raw.get("description"), str) and raw.get("description").strip()
                else listing.description
            )
            title = TitleBuilder.fit([title], listing.title_limit)
            description = DescriptionBuilder._cap(description, listing.description_limit)
            updated.append(replace(listing, title=title, description=description, polish="applied"))
        return tuple(updated)
