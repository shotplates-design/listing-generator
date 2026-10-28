"""The instruction sent with the photos. Temperature stays at 0; the parser still refuses guesses."""


class VisionPrompt:
    @staticmethod
    def extraction() -> str:
        return """You read photos of one clothing item for a resale listing. Return one JSON object and nothing else.

Every field is an object: {"value": string or null, "confidence": "high" | "medium" | "low" | "none", "evidence": a short phrase}.

Rules:
- Use high only when the photo shows the fact clearly.
- If you are not sure, use low or none and set value to null. Do not guess.
- Brand only from a readable label, a logo you can name, or a brand mark.
- Size only from a readable tag. Do not infer size from how big the garment looks.
- Material only from a readable content or care tag. Do not infer fabric from drape or sheen.
- Color may come from the garment when the photo shows it clearly. If it could be either of two colors, use null.
- Flaws: describe only wear you can see. If you cannot see a defect, flaws value is null. Never claim the item is unworn or flawless.
- gender_department only from an explicit printed label such as Men's or Women's. Otherwise null. Allowed values: mens, womens, unisex, boys, girls, kids.
- style_era only when the look is distinctive. Otherwise null.
- measurements must be null unless a ruler or tape is visible. Never estimate a measurement from how big the garment looks. When you can read the ruler, set each measurement you can see, such as pit_to_pit "23 in" and length "27 in", and mention the ruler in evidence. Use a range and confidence medium only when the span falls between two marks.
- condition, if set, must be one of: new_with_tags, new_without_tags, excellent, good, fair, poor.
- origin only from a readable "made in" stamp. Otherwise null.
- Do not invent a price.

Fields: brand, item_type, size_tagged, color, material, origin, condition, flaws, style_era, gender_department, measurements.
"""

    @staticmethod
    def polish(drafts: str) -> str:
        return (
            "Rewrite these resale listing drafts so they read more naturally. "
            "Return one JSON object whose keys are the platform ids and whose values are "
            '{"title": string, "description": string}. '
            "Do not add facts, measurements, brands, sizes, materials, or condition claims that are not already in the draft. "
            "Do not remove flaws. Keep each title within the character limit given in the draft. "
            "If a fact is missing, leave it missing.\n\n"
            + drafts
        )
