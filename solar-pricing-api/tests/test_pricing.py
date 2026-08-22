"""
Unit tests for the pricing engine — independent of FastAPI.

Covers:
* α(q) behaviour (monotonicity, limits)
* Dynamic rate bounds (P_export ≤ P_solar ≤ P_grid)
* Tenant savings invariants
* Landlord revenue invariants
* Edge cases (zero usage, no solar, excess solar, excess demand)
* Export > grid rate rejection
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta

import pytest

from app.pricing import (
    calculate_alpha,
    calculate_dynamic_rate,
    calculate_interval_price,
    cents_to_dollars,
)

# ── Helpers ───────────────────────────────────────────────────────────────

AEST = timezone(timedelta(hours=10))
MIDDAY = datetime(2026, 8, 22, 12, 30, tzinfo=AEST)   # 10–14 TOU window
PEAK   = datetime(2026, 8, 22, 18, 0, tzinfo=AEST)     # 16–20 TOU window

ALPHA_MIN = 0.40
ALPHA_MAX = 0.75
K = 0.50


# ═══════════════════════════════════════════════════════════════════════════
# cents_to_dollars
# ═══════════════════════════════════════════════════════════════════════════


class TestCentsToDollars:
    def test_basic_conversion(self) -> None:
        assert cents_to_dollars(100) == 1.0

    def test_zero(self) -> None:
        assert cents_to_dollars(0) == 0.0

    def test_fractional(self) -> None:
        assert cents_to_dollars(12.35) == pytest.approx(0.1235)


# ═══════════════════════════════════════════════════════════════════════════
# α(q) — share factor
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculateAlpha:
    def test_at_zero_usage_equals_alpha_max(self) -> None:
        """Test 6: α(0) → α_max."""
        alpha = calculate_alpha(0.0, ALPHA_MIN, ALPHA_MAX, K)
        assert alpha == pytest.approx(ALPHA_MAX)

    def test_at_very_high_usage_approaches_alpha_min(self) -> None:
        """Test 5: α(q) → α_min as q → ∞."""
        alpha = calculate_alpha(100.0, ALPHA_MIN, ALPHA_MAX, K)
        assert alpha == pytest.approx(ALPHA_MIN, abs=1e-6)

    def test_monotonically_decreasing(self) -> None:
        """Test 1: higher usage → lower α."""
        usages = [0.5, 1.0, 2.0, 5.0, 10.0]
        alphas = [calculate_alpha(q, ALPHA_MIN, ALPHA_MAX, K) for q in usages]
        for i in range(len(alphas) - 1):
            assert alphas[i] > alphas[i + 1], (
                f"α should decrease: α({usages[i]})={alphas[i]} "
                f"vs α({usages[i+1]})={alphas[i+1]}"
            )

    def test_alpha_within_bounds(self) -> None:
        for q in [0.0, 0.1, 1.0, 5.0, 50.0]:
            alpha = calculate_alpha(q, ALPHA_MIN, ALPHA_MAX, K)
            assert ALPHA_MIN <= alpha <= ALPHA_MAX

    def test_known_value(self) -> None:
        """Verify against hand-calculated value."""
        expected = ALPHA_MIN + (ALPHA_MAX - ALPHA_MIN) * math.exp(-K * 2.5)
        actual = calculate_alpha(2.5, ALPHA_MIN, ALPHA_MAX, K)
        assert actual == pytest.approx(expected)


# ═══════════════════════════════════════════════════════════════════════════
# Dynamic rate bounds
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculateDynamicRate:
    @pytest.mark.parametrize("usage", [0.0, 0.5, 1.0, 2.5, 10.0, 50.0])
    def test_rate_between_export_and_grid(self, usage: float) -> None:
        """Test 2: P_export ≤ P_solar ≤ P_grid for all usage levels."""
        grid_rate = 12.35
        export_rate = 3.2
        solar_rate, _ = calculate_dynamic_rate(
            usage, grid_rate, export_rate, ALPHA_MIN, ALPHA_MAX, K
        )
        assert export_rate <= solar_rate <= grid_rate

    def test_higher_usage_gives_lower_rate(self) -> None:
        """Test 1: increasing usage → decreasing solar rate."""
        grid_rate = 46.85
        export_rate = 18.0
        usages = [0.5, 1.0, 2.0, 5.0, 10.0]
        rates = [
            calculate_dynamic_rate(
                q, grid_rate, export_rate, ALPHA_MIN, ALPHA_MAX, K
            )[0]
            for q in usages
        ]
        for i in range(len(rates) - 1):
            assert rates[i] > rates[i + 1]

    def test_equal_export_and_grid_rate(self) -> None:
        """When export == grid, solar rate equals both."""
        rate = 20.0
        solar_rate, _ = calculate_dynamic_rate(
            2.5, rate, rate, ALPHA_MIN, ALPHA_MAX, K
        )
        assert solar_rate == pytest.approx(rate)


# ═══════════════════════════════════════════════════════════════════════════
# Full interval calculation
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculateIntervalPrice:

    # ── Zero usage ────────────────────────────────────────────────────────

    def test_zero_usage_zero_charge(self) -> None:
        """Zero usage → $0 charge."""
        result = calculate_interval_price(
            usage_kwh=0.0,
            solar_available_kwh=0.0,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
        )
        assert result.total_charge_dollars == 0.0
        assert result.tenant_saving_dollars == 0.0

    # ── No solar available ────────────────────────────────────────────────

    def test_no_solar_all_grid(self) -> None:
        """When solar_available=0, all usage comes from grid."""
        result = calculate_interval_price(
            usage_kwh=3.0,
            solar_available_kwh=0.0,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
        )
        assert result.solar_usage_kwh == 0.0
        assert result.grid_usage_kwh == 3.0
        assert result.solar_charge_dollars == 0.0
        assert result.grid_charge_dollars > 0
        # No tenant saving when everything is from the grid
        assert result.tenant_saving_dollars == pytest.approx(0.0, abs=1e-9)

    # ── Solar > demand ────────────────────────────────────────────────────

    def test_excess_solar(self) -> None:
        """Solar exceeds demand → solar_usage = usage, grid_usage = 0."""
        result = calculate_interval_price(
            usage_kwh=2.5,
            solar_available_kwh=5.0,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
        )
        assert result.solar_usage_kwh == 2.5
        assert result.grid_usage_kwh == 0.0

    # ── Demand > solar ────────────────────────────────────────────────────

    def test_demand_exceeds_solar(self) -> None:
        """Usage exceeds solar → remainder from grid."""
        result = calculate_interval_price(
            usage_kwh=5.0,
            solar_available_kwh=2.0,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
        )
        assert result.solar_usage_kwh == 2.0
        assert result.grid_usage_kwh == 3.0
        assert result.grid_charge_dollars > 0

    # ── Tenant savings invariants ─────────────────────────────────────────

    def test_tenant_savings_non_negative_full_solar(self) -> None:
        """Test 3: Savings ≥ 0 when all usage is solar-covered."""
        result = calculate_interval_price(
            usage_kwh=2.5,
            solar_available_kwh=3.0,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
        )
        assert result.tenant_saving_dollars >= 0

    @pytest.mark.parametrize(
        "usage,solar",
        [(0.5, 1.0), (1.0, 1.0), (2.5, 3.0), (5.0, 10.0), (10.0, 10.0)],
    )
    def test_tenant_savings_always_non_negative_dynamic(
        self, usage: float, solar: float
    ) -> None:
        """Test 3 (parameterised): savings never negative for solar-covered usage."""
        result = calculate_interval_price(
            usage_kwh=usage,
            solar_available_kwh=solar,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
        )
        assert result.tenant_saving_dollars >= -1e-9

    # ── Landlord revenue invariants ───────────────────────────────────────

    def test_landlord_revenue_at_least_export_value(self) -> None:
        """Test 4: Landlord solar revenue ≥ export value."""
        result = calculate_interval_price(
            usage_kwh=2.5,
            solar_available_kwh=3.0,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
        )
        assert result.solar_charge_dollars >= result.landlord_export_value_dollars
        assert result.landlord_additional_revenue_dollars >= -1e-9

    # ── Fixed mode ────────────────────────────────────────────────────────

    def test_fixed_mode_uses_fixed_rate(self) -> None:
        result = calculate_interval_price(
            usage_kwh=2.0,
            solar_available_kwh=5.0,
            timestamp=MIDDAY,
            pricing_mode="fixed",
            fixed_solar_rate=22.0,
        )
        assert result.solar_rate_cents_per_kwh == 22.0
        assert result.alpha is None
        expected_charge = cents_to_dollars(2.0 * 22.0)
        assert result.solar_charge_dollars == pytest.approx(expected_charge)

    # ── Rate overrides ────────────────────────────────────────────────────

    def test_manual_rate_override(self) -> None:
        result = calculate_interval_price(
            usage_kwh=2.0,
            solar_available_kwh=3.0,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
            grid_rate_override=30.0,
            export_rate_override=5.0,
        )
        assert result.grid_rate_cents_per_kwh == 30.0
        assert result.export_rate_cents_per_kwh == 5.0

    # ── Export > grid rate → ValueError ───────────────────────────────────

    def test_export_exceeds_grid_raises(self) -> None:
        with pytest.raises(ValueError, match="Export rate cannot exceed grid rate"):
            calculate_interval_price(
                usage_kwh=1.0,
                solar_available_kwh=2.0,
                timestamp=MIDDAY,
                pricing_mode="dynamic",
                grid_rate_override=10.0,
                export_rate_override=20.0,
            )

    # ── solar_available_kwh omitted ───────────────────────────────────────

    def test_solar_available_none(self) -> None:
        """When solar_available_kwh is None, all usage treated as solar."""
        result = calculate_interval_price(
            usage_kwh=2.0,
            solar_available_kwh=None,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
        )
        assert result.solar_usage_kwh == 2.0
        assert result.grid_usage_kwh == 0.0

    # ── Example from specification ────────────────────────────────────────

    def test_spec_example(self) -> None:
        """Verify the example calculation from the spec (section 12)."""
        result = calculate_interval_price(
            usage_kwh=2.5,
            solar_available_kwh=3.0,
            timestamp=MIDDAY,
            pricing_mode="dynamic",
            grid_rate_override=12.35,
            export_rate_override=3.2,
            alpha_min=0.40,
            alpha_max=0.75,
            discount_sensitivity=0.50,
        )

        # α(2.5) = 0.40 + 0.35 × e^(−0.5 × 2.5)
        expected_alpha = 0.40 + 0.35 * math.exp(-0.5 * 2.5)
        assert result.alpha == pytest.approx(expected_alpha, abs=1e-3)

        # P_solar = 3.2 + α × (12.35 − 3.2)
        expected_rate = 3.2 + expected_alpha * (12.35 - 3.2)
        assert result.solar_rate_cents_per_kwh == pytest.approx(
            expected_rate, abs=0.1
        )

        # All usage from solar, none from grid
        assert result.solar_usage_kwh == 2.5
        assert result.grid_usage_kwh == 0.0
        assert result.tenant_saving_dollars > 0
        assert result.landlord_additional_revenue_dollars > 0
