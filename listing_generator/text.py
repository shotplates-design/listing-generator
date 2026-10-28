"""Small text helpers shared by titles, descriptions, and the parser."""

from __future__ import annotations

import re


class Text:
    _PLACEHOLDERS = {
        "unknown",
        "n/a",
        "na",
        "none",
        "null",
        "unsure",
        "unclear",
        "not sure",
        "cannot tell",
        "can't tell",
        "not visible",
        "unreadable",
        "tbd",
        "?",
        "-",
    }

    @staticmethod
    def squash(value: object) -> str:
        if value is None:
            return ""
        text = " ".join(str(value).replace("\n", " ").split())
        return text.strip().strip("\"'`")

    @staticmethod
    def is_placeholder(value: str) -> bool:
        return value.strip().lower() in Text._PLACEHOLDERS

    @staticmethod
    def dedupe(parts: list[str]) -> list[str]:
        seen: set[str] = set()
        kept: list[str] = []
        for part in parts:
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            kept.append(part)
        return kept

    @staticmethod
    def label(value: str) -> str:
        """Light label case that leaves existing capitals and leading digits alone."""
        text = Text.squash(value)
        if not text:
            return ""
        words = []
        for word in text.split(" "):
            if "-" in word:
                words.append("-".join(Text._cap_token(piece) for piece in word.split("-")))
            else:
                words.append(Text._cap_token(word))
        return " ".join(words)

    @staticmethod
    def _cap_token(word: str) -> str:
        if not word or any(character.isupper() for character in word) or word[:1].isdigit():
            return word
        return word[:1].upper() + word[1:]

    @staticmethod
    def hashtag(value: str) -> str:
        token = re.sub(r"[^a-z0-9]", "", value.lower())
        if not token:
            return ""
        return f"#{token}"


class Departments:
    CHOICES = (
        ("", "Not set"),
        ("mens", "Men's"),
        ("womens", "Women's"),
        ("unisex", "Unisex"),
        ("boys", "Boys'"),
        ("girls", "Girls'"),
        ("kids", "Kids'"),
    )

    _ALIASES = {
        "men": "mens",
        "mens": "mens",
        "men's": "mens",
        "male": "mens",
        "man": "mens",
        "women": "womens",
        "womens": "womens",
        "women's": "womens",
        "female": "womens",
        "woman": "womens",
        "unisex": "unisex",
        "boys": "boys",
        "boy": "boys",
        "boy's": "boys",
        "girls": "girls",
        "girl": "girls",
        "girl's": "girls",
        "kids": "kids",
        "kid": "kids",
        "kid's": "kids",
        "youth": "kids",
        "child": "kids",
        "children": "kids",
    }

    @staticmethod
    def normalize(value: str) -> str | None:
        key = Text.squash(value).lower().replace("’", "'")
        if not key or Text.is_placeholder(key):
            return None
        return Departments._ALIASES.get(key)

    @staticmethod
    def display(value: str) -> str:
        if not value:
            return ""
        for key, label in Departments.CHOICES:
            if key == value:
                return label
        return ""

    @staticmethod
    def adjective(value: str) -> str:
        return Departments.display(value).lower()


class Conditions:
    CHOICES = (
        ("", "Not set"),
        ("new_with_tags", "New with tags"),
        ("new_without_tags", "New without tags"),
        ("excellent", "Excellent"),
        ("good", "Good"),
        ("fair", "Fair"),
        ("poor", "Poor"),
    )

    _ALIASES = {
        "new with tags": "new_with_tags",
        "new_with_tags": "new_with_tags",
        "nwt": "new_with_tags",
        "brand new": "new_with_tags",
        "new with tag": "new_with_tags",
        "new without tags": "new_without_tags",
        "new_without_tags": "new_without_tags",
        "nwot": "new_without_tags",
        "new without tag": "new_without_tags",
        "excellent": "excellent",
        "like new": "excellent",
        "like_new": "excellent",
        "used-excellent": "excellent",
        "good": "good",
        "very good": "good",
        "fair": "fair",
        "acceptable": "fair",
        "poor": "poor",
    }

    _PLATFORM = {
        "new_with_tags": {
            "ebay": "New with tags",
            "poshmark": "NWT",
            "depop": "Brand new",
            "mercari": "New",
            "whatnot": "New",
            "facebook_marketplace": "New",
            "title": "NWT",
        },
        "new_without_tags": {
            "ebay": "New without tags",
            "poshmark": "NWOT",
            "depop": "Like new",
            "mercari": "Like new",
            "whatnot": "New without tags",
            "facebook_marketplace": "Used - Like New",
            "title": "NWOT",
        },
        "excellent": {
            "ebay": "Pre-owned — Excellent",
            "poshmark": "Excellent",
            "depop": "Excellent",
            "mercari": "Like new",
            "whatnot": "Excellent",
            "facebook_marketplace": "Used - Like New",
            "title": "Excellent",
        },
        "good": {
            "ebay": "Pre-owned — Good",
            "poshmark": "Good",
            "depop": "Good",
            "mercari": "Good",
            "whatnot": "Good",
            "facebook_marketplace": "Used - Good",
            "title": "Good",
        },
        "fair": {
            "ebay": "Pre-owned — Fair",
            "poshmark": "Fair",
            "depop": "Fair",
            "mercari": "Fair",
            "whatnot": "Fair",
            "facebook_marketplace": "Used - Fair",
            "title": "Fair",
        },
        "poor": {
            "ebay": "Pre-owned — Poor",
            "poshmark": "Poor",
            "depop": "Poor",
            "mercari": "Poor",
            "whatnot": "Poor",
            "facebook_marketplace": "Used - Fair",
            "title": "Poor",
        },
    }

    @staticmethod
    def normalize(value: str) -> str | None:
        key = Text.squash(value).lower().replace("-", " ").replace("_", " ")
        key = " ".join(key.split())
        if not key or Text.is_placeholder(key):
            return None
        if key in Conditions._ALIASES:
            return Conditions._ALIASES[key]
        return Conditions._ALIASES.get(key.replace(" ", "_"))

    @staticmethod
    def label(value: str) -> str:
        if not value:
            return ""
        for key, label in Conditions.CHOICES:
            if key == value:
                return label
        return ""

    @staticmethod
    def platform_label(value: str, platform: str) -> str:
        row = Conditions._PLATFORM.get(value)
        if not row:
            return ""
        return row.get(platform, "")

    @staticmethod
    def title_token(value: str) -> str:
        row = Conditions._PLATFORM.get(value)
        if not row:
            return ""
        return row["title"]
