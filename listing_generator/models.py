"""Data the rest of the app passes around."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


class Platforms:
    """Marketplace ids, in the order the app shows them."""

    ORDER = ("ebay", "poshmark", "depop", "mercari", "whatnot", "facebook_marketplace")


class Fields:
    """Form fields the vision step can fill or leave blank."""

    EXTRACTED = (
        "brand",
        "item_type",
        "size_tagged",
        "color",
        "material",
        "condition",
        "flaws",
        "style_era",
        "gender_department",
        "measurements",
    )

    LABELS = {
        "brand": "Brand",
        "item_type": "Item type",
        "size_tagged": "Size on tag",
        "color": "Color",
        "material": "Material",
        "condition": "Condition",
        "flaws": "Flaws",
        "style_era": "Style or era",
        "gender_department": "Department",
        "measurements": "Measurements",
    }

    MEASUREMENTS = (
        ("pit_to_pit", "Pit to pit"),
        ("length", "Length"),
        ("shoulders", "Shoulders"),
        ("sleeve", "Sleeve"),
        ("waist", "Waist"),
        ("inseam", "Inseam"),
        ("rise", "Rise"),
        ("other", "Other"),
    )


@dataclass
class ClothingItem:
    """Seller-confirmed facts. Empty strings mean unknown, not a guess."""

    brand: str = ""
    item_type: str = ""
    size_tagged: str = ""
    color: str = ""
    material: str = ""
    origin: str = ""
    condition: str = ""
    flaws: str = ""
    style_era: str = ""
    gender_department: str = ""
    measurements: dict[str, str] = field(default_factory=dict)
    cost_basis: Decimal | None = None
    target_price: Decimal | None = None
    buyer_paid_shipping: Decimal | None = None
    sales_tax: Decimal | None = None
    facebook_fulfillment: str = "local_pickup"
    field_flags: dict[str, str] = field(default_factory=dict)
    field_confidence: dict[str, str] = field(default_factory=dict)
    review_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "brand": self.brand,
            "item_type": self.item_type,
            "size_tagged": self.size_tagged,
            "color": self.color,
            "material": self.material,
            "origin": self.origin,
            "condition": self.condition,
            "flaws": self.flaws,
            "style_era": self.style_era,
            "gender_department": self.gender_department,
            "measurements": dict(self.measurements),
            "cost_basis": _money_out(self.cost_basis),
            "target_price": _money_out(self.target_price),
            "buyer_paid_shipping": _money_out(self.buyer_paid_shipping),
            "sales_tax": _money_out(self.sales_tax),
            "facebook_fulfillment": self.facebook_fulfillment,
            "field_flags": dict(self.field_flags),
            "field_confidence": dict(self.field_confidence),
            "review_notes": list(self.review_notes),
        }

    @staticmethod
    def from_dict(data: dict) -> ClothingItem:
        from listing_generator.money import Money

        measurements = data.get("measurements") or {}
        if not isinstance(measurements, dict):
            measurements = {}
        flags = data.get("field_flags") or {}
        confidence = data.get("field_confidence") or {}
        notes = data.get("review_notes") or []
        return ClothingItem(
            brand=str(data.get("brand") or ""),
            item_type=str(data.get("item_type") or ""),
            size_tagged=str(data.get("size_tagged") or ""),
            color=str(data.get("color") or ""),
            material=str(data.get("material") or ""),
            origin=str(data.get("origin") or ""),
            condition=str(data.get("condition") or ""),
            flaws=str(data.get("flaws") or ""),
            style_era=str(data.get("style_era") or ""),
            gender_department=str(data.get("gender_department") or ""),
            measurements={str(k): str(v) for k, v in measurements.items() if str(v).strip()},
            cost_basis=Money.parse(data.get("cost_basis")),
            target_price=Money.parse(data.get("target_price")),
            buyer_paid_shipping=Money.parse(data.get("buyer_paid_shipping")),
            sales_tax=Money.parse(data.get("sales_tax")),
            facebook_fulfillment=FacebookFulfillment.normalize(data.get("facebook_fulfillment")),
            field_flags={str(k): str(v) for k, v in flags.items()} if isinstance(flags, dict) else {},
            field_confidence={str(k): str(v) for k, v in confidence.items()} if isinstance(confidence, dict) else {},
            review_notes=[str(note) for note in notes] if isinstance(notes, list) else [],
        )


class FacebookFulfillment:
    """How a Facebook Marketplace draft would be handed to the buyer."""

    CHOICES = (
        ("local_pickup", "Local pickup (no fee)"),
        ("shipped", "Shipped (selling fee, verify the rate)"),
    )

    @staticmethod
    def normalize(value: object) -> str:
        if str(value or "").strip() == "shipped":
            return "shipped"
        return "local_pickup"


class PhotoRoles:
    """Roles a crosslisting app can rely on."""

    CHOICES = ("front", "back", "tag", "flaw", "detail")

    @staticmethod
    def default_for_index(index: int) -> str:
        if index < len(PhotoRoles.CHOICES):
            return PhotoRoles.CHOICES[index]
        return "detail"

    @staticmethod
    def normalize(value: str) -> str:
        key = str(value or "").strip().lower()
        if key in PhotoRoles.CHOICES:
            return key
        return "detail"


@dataclass(frozen=True)
class PhotoRef:
    path_or_url: str
    role: str
    order: int


@dataclass(frozen=True)
class DiscardedReading:
    field: str
    value: str
    confidence: str
    evidence: str
    reason: str


@dataclass
class ExtractionResult:
    item: ClothingItem
    discarded: list[DiscardedReading]
    provider: str
    model: str


@dataclass(frozen=True)
class FeeLine:
    label: str
    amount: Decimal


@dataclass(frozen=True)
class FeeBreakdown:
    platform: str
    list_price: Decimal
    fee_base: Decimal
    lines: tuple[FeeLine, ...]
    total_fee: Decimal
    net: Decimal
    formula: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class PlatformListing:
    platform: str
    display_name: str
    title: str
    title_limit: int
    description: str
    description_limit: int
    category: str
    category_note: str
    tags_label: str
    tags: tuple[str, ...]
    item_specifics: tuple[tuple[str, str], ...]
    missing_specifics: tuple[str, ...]
    list_price: Decimal | None
    price_rationale: str
    fee: FeeBreakdown | None
    equalized_list_price: Decimal | None
    equalized_note: str
    checklist: tuple[str, ...]
    polish: str


def _money_out(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value.quantize(Decimal('0.01')):.2f}"
