from decimal import Decimal

import pytest

from listing_generator.models import ClothingItem


@pytest.fixture
def hoodie() -> ClothingItem:
    return ClothingItem(
        brand="Nike",
        item_type="hoodie",
        gender_department="mens",
        size_tagged="M",
        color="navy",
        material="cotton blend",
        condition="good",
        flaws="Small hole near the left hem",
        style_era="90s athletic",
        target_price=Decimal("40.00"),
        cost_basis=Decimal("18.00"),
    )
