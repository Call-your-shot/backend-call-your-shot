from decimal import Decimal

import pytest

from app.green_credits import (
    credits_to_microcredits,
    microcredits_to_credits,
    solar_kwh_to_microcredits,
    split_green_credits,
)
from app.schemas import EnergyReadingInput


def test_credit_unit_conversion_is_exact_and_display_stable():
    assert credits_to_microcredits("1") == 1_000_000
    assert credits_to_microcredits("0.1234564") == 123_456
    assert credits_to_microcredits("0.1234565") == 123_457
    assert microcredits_to_credits(1_234_567) == "1.234567"
    assert microcredits_to_credits(-500_000) == "-0.500000"


@pytest.mark.parametrize("value", ["0", "-1", "nan", "Infinity"])
def test_requested_credits_must_be_positive_and_finite(value):
    with pytest.raises(ValueError):
        credits_to_microcredits(value)


def test_verified_solar_kwh_maps_to_one_credit_per_kwh():
    assert solar_kwh_to_microcredits(Decimal("2.375")) == 2_375_000
    assert solar_kwh_to_microcredits(0) == 0


def test_negative_solar_consumption_is_rejected():
    with pytest.raises(ValueError):
        solar_kwh_to_microcredits(-0.01)


def test_default_split_is_70_percent_tenant_30_percent_owner():
    result = split_green_credits(
        1_000_000,
        tenant_user_ids=["tenant"],
        owner_user_ids=["owner"],
    )

    assert [(item.role, item.amount_microcredits) for item in result.allocations] == [
        ("tenant", 700_000),
        ("landlord", 300_000),
    ]
    assert result.unissued_microcredits == 0


def test_role_shares_are_equal_and_rounding_is_deterministic():
    result = split_green_credits(
        11,
        tenant_user_ids=["tenant-b", "tenant-a"],
        owner_user_ids=["owner-b", "owner-a"],
    )

    assert [
        (item.user_id, item.amount_microcredits) for item in result.allocations
    ] == [
        ("tenant-a", 4),
        ("tenant-b", 3),
        ("owner-a", 2),
        ("owner-b", 2),
    ]
    assert sum(item.amount_microcredits for item in result.allocations) == 11


def test_missing_role_is_unissued_and_not_reassigned():
    result = split_green_credits(
        1_000_000,
        tenant_user_ids=["tenant"],
        owner_user_ids=[],
    )

    assert sum(item.amount_microcredits for item in result.allocations) == 700_000
    assert result.unissued_microcredits == 300_000


def test_duplicate_member_ids_do_not_receive_duplicate_shares():
    result = split_green_credits(
        1_000_000,
        tenant_user_ids=["tenant", "tenant"],
        owner_user_ids=["owner"],
    )
    assert len(result.allocations) == 2


def test_invalid_share_configuration_is_rejected():
    with pytest.raises(ValueError):
        split_green_credits(100, ["tenant"], ["owner"], 6_000, 3_000)


def test_rewardable_solar_consumption_cannot_exceed_generation():
    with pytest.raises(ValueError, match="cannot exceed interval solar generation"):
        EnergyReadingInput(
            intervalStart="2026-08-22T00:00:00Z",
            intervalEnd="2026-08-22T01:00:00Z",
            consumptionKwh=2,
            solarGenerationKwh=1,
            solarConsumedByTenantKwh=1.5,
        )
