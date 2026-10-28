"""Category suggestions. These are paths to confirm in each app, not live category ids."""

from __future__ import annotations

from dataclasses import dataclass

from listing_generator.models import ClothingItem
from listing_generator.text import Departments, Text


@dataclass(frozen=True)
class CategorySuggestion:
    path: str
    note: str


class CategorySuggester:
    """Maps an item type onto a readable category path for each platform."""

    _RULES = (
        (("hoodie", "sweatshirt"), "Hoodies & Sweatshirts", "tops"),
        (("t-shirt", "tee", "tshirt"), "T-Shirts", "tops"),
        (("polo",), "Polos", "tops"),
        (("blouse",), "Blouses", "tops"),
        (("tank",), "Tanks", "tops"),
        (("sweater", "cardigan"), "Sweaters", "tops"),
        (("shirt",), "Shirts", "tops"),
        (("jeans",), "Jeans", "bottoms"),
        (("pants", "trousers"), "Pants", "bottoms"),
        (("shorts",), "Shorts", "bottoms"),
        (("skirt",), "Skirts", "bottoms"),
        (("dress",), "Dresses", "dresses"),
        (("jumpsuit", "romper"), "Jumpsuits & Rompers", "dresses"),
        (("blazer", "suit jacket"), "Blazers", "outerwear"),
        (("jacket", "coat"), "Jackets & Coats", "outerwear"),
        (("sneaker", "athletic shoe", "running shoe", "trainer"), "Athletic Shoes", "shoes"),
        (("boot",), "Boots", "shoes"),
        (("sandal",), "Sandals", "shoes"),
        (("shoe",), "Shoes", "shoes"),
        (("handbag", "purse", "shoulder bag"), "Bags & Handbags", "bags"),
        (("hat", "cap", "beanie"), "Hats", "accessories"),
        (("scarf",), "Scarves", "accessories"),
    )

    @staticmethod
    def suggest(item: ClothingItem) -> dict[str, CategorySuggestion]:
        leaf, group, matched = CategorySuggester._match(item.item_type)
        note = "Confirm this category in the app. It is a suggestion, not a live category id."
        if not matched:
            note = "Item type did not match a known category. Pick one in the app. " + note
        if not item.gender_department:
            note = "Department is blank, so the path stays general. Set it before you post. " + note
        department = Departments.display(item.gender_department)
        return {
            "ebay": CategorySuggestion(CategorySuggester._ebay(department, leaf, group), note),
            "poshmark": CategorySuggestion(CategorySuggester._posh(department, leaf, group), note),
            "depop": CategorySuggestion(CategorySuggester._depop(department, group), note),
            "mercari": CategorySuggestion(CategorySuggester._mercari(department, leaf), note),
            "whatnot": CategorySuggestion(f"Clothing / {leaf}", note),
            "facebook_marketplace": CategorySuggestion(CategorySuggester._facebook(department, leaf, group), note),
        }

    @staticmethod
    def _facebook(department: str, leaf: str, group: str) -> str:
        if group == "shoes":
            return f"Apparel & accessories > Shoes > {leaf}"
        if group == "bags":
            return "Apparel & accessories > Bags & luggage"
        if department:
            return f"Apparel & accessories > {department} clothing > {leaf}"
        return f"Apparel & accessories > Clothing > {leaf}"

    @staticmethod
    def _match(item_type: str) -> tuple[str, str, bool]:
        text = Text.squash(item_type).lower()
        if not text:
            return "Clothing", "clothing", False
        for phrases, leaf, group in CategorySuggester._RULES:
            for phrase in phrases:
                if phrase in text:
                    return leaf, group, True
        return "Clothing", "clothing", False

    @staticmethod
    def _ebay(department: str, leaf: str, group: str) -> str:
        root = "Clothing, Shoes & Accessories"
        if group == "bags":
            return f"{root} > Women > Women's Bags & Handbags"
        if group == "shoes":
            if department == "Women's":
                return f"{root} > Women > Women's Shoes > {leaf}"
            if department == "Men's":
                return f"{root} > Men > Men's Shoes > {leaf}"
            if department:
                return f"{root} > {department} > Shoes > {leaf}"
            return f"{root} > Shoes > {leaf}"
        if not department:
            return f"{root} > {leaf}"
        clothing = {
            "Men's": "Men > Men's Clothing",
            "Women's": "Women > Women's Clothing",
            "Boys'": "Boys > Boys' Clothing",
            "Girls'": "Girls > Girls' Clothing",
            "Kids'": "Kids > Kids' Clothing",
            "Unisex": "Unisex Clothing",
        }.get(department, department)
        return f"{root} > {clothing} > {leaf}"

    @staticmethod
    def _posh(department: str, leaf: str, group: str) -> str:
        dept = department or "All"
        group_label = {
            "tops": "Tops",
            "bottoms": "Bottoms",
            "dresses": "Dresses",
            "outerwear": "Jackets & Coats",
            "shoes": "Shoes",
            "bags": "Bags",
            "accessories": "Accessories",
            "clothing": "Clothing",
        }[group]
        if group in {"dresses", "shoes", "bags", "accessories"}:
            return f"{dept} > {leaf}"
        return f"{dept} > {group_label} > {leaf}"

    @staticmethod
    def _depop(department: str, group: str) -> str:
        group_label = {
            "tops": "Tops",
            "bottoms": "Bottoms",
            "dresses": "Dresses",
            "outerwear": "Outerwear",
            "shoes": "Footwear",
            "bags": "Bags",
            "accessories": "Accessories",
            "clothing": "Clothing",
        }[group]
        if department == "Men's":
            return f"Menswear > {group_label}"
        if department == "Women's":
            return f"Womenswear > {group_label}"
        if department:
            return f"{department} > {group_label}"
        return group_label

    @staticmethod
    def _mercari(department: str, leaf: str) -> str:
        if department:
            return f"{department} > Clothing > {leaf}"
        return f"Clothing > {leaf}"
