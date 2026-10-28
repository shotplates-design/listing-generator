"""Platform constraints applied to every draft, including text that came back from polish."""

from __future__ import annotations

import re
from dataclasses import replace

from listing_generator.descriptions import DescriptionBuilder
from listing_generator.models import PlatformListing
from listing_generator.titles import TitleBuilder


class PlatformRules:
    """Title limits and marketplace copy rules. Polish cannot leave these behind."""

    @staticmethod
    def enforce(listing: PlatformListing) -> PlatformListing:
        title = listing.title
        description = listing.description
        if listing.platform == "facebook_marketplace":
            title = PlatformRules.strip_hashtags(title)
            description = PlatformRules.strip_hashtags(description)
        if not title.strip():
            title = "Clothing"
        if not description.strip():
            description = "Clothing"
        title = TitleBuilder.fit([title], listing.title_limit)
        description = DescriptionBuilder._cap(description, listing.description_limit)
        if listing.platform == "facebook_marketplace":
            title = title.replace("#", "")
            description = description.replace("#", "")
            if not title.strip():
                title = "Clothing"[: listing.title_limit]
            if not description.strip():
                description = "Clothing"[: listing.description_limit]
        return replace(listing, title=title, description=description)

    @staticmethod
    def strip_hashtags(text: str) -> str:
        lines = []
        for line in text.splitlines():
            without_tags = re.sub(r"#\w+", "", line)
            without_marks = without_tags.replace("#", "")
            lines.append(re.sub(r"[ \t]{2,}", " ", without_marks).rstrip())
        return "\n".join(lines).strip()
