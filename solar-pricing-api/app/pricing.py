"""
Core pricing engine for solar-to-tenant electricity pricing.

All functions in this module are **pure** (aside from tariff resolution) and
do not depend on FastAPI.  They can be unit-tested independently.

Conventions
-----------
* Rates are always in *cents per kWh*.
* Charges / costs / savings are in *Australian dollars*.
"""

import math
from datetime import datetime
from typing import Optional, Tuple

from app.models import PricingResult
from app.tariffs import resolve_export_rate, resolve_grid_rate


# ═══════════════════════════════════════════════════════════════════════════
# Unit helpers
# ═══════════════════════════════════════════════════════════════════════════


def cents_to_dollars(cents: float) -> float:
    """Convert a value in cents to Australian dollars."""
    return cents / 100.0


# ═══════════════════════════════════════════════════════════════════════════
# α(q) — Landlord share factor
# ═══════════════════════════════════════════════════════════════════════════


def calculate_alpha(
    usage_kwh: float,
    alpha_min: float,
    alpha_max: float,
    sensitivity: float,
) -> float:
    """
    Calculate the landlord's share factor α(q).

    .. math::

        \\alpha(q) = \\alpha_{\\min}
                   + (\\alpha_{\\max} - \\alpha_{\\min})\\,e^{-k\\,q}

    As *usage_kwh* increases, α decays from ``alpha_max`` towards
    ``alpha_min``, giving the tenant a progressively better price.

    Parameters
    ----------
    usage_kwh:
        Solar electricity consumed by the tenant (kWh).
    alpha_min:
        Landlord share floor (approached at high usage).
    alpha_max:
        Landlord share ceiling (used at near-zero usage).
    sensitivity:
        Exponential decay constant *k* (must be > 0).

    Returns
    -------
    float
        The share factor α in the range [alpha_min, alpha_max].
    """
    return alpha_min + (alpha_max - alpha_min) * math.exp(-sensitivity * usage_kwh)


# ═══════════════════════════════════════════════════════════════════════════
# Dynamic solar rate
# ═══════════════════════════════════════════════════════════════════════════


def calculate_dynamic_rate(
    usage_kwh: float,
    grid_rate: float,
    export_rate: float,
    alpha_min: float,
    alpha_max: float,
    sensitivity: float,
) -> Tuple[float, float]:
    """
    Calculate the dynamic tenant solar rate P_solar(t, q).

    .. math::

        P_{solar}(t,q) = P_{export}(t)
                       + \\alpha(q)\\,[P_{grid}(t) - P_{export}(t)]

    The result is defensively clamped to ``[P_export, P_grid]``.

    Parameters
    ----------
    usage_kwh:
        Solar electricity consumed (kWh).
    grid_rate:
        Grid electricity rate at the relevant time (cents/kWh).
    export_rate:
        Solar export / feed-in tariff rate (cents/kWh).
    alpha_min, alpha_max:
        Bounds for the share factor.
    sensitivity:
        Decay constant *k*.

    Returns
    -------
    Tuple[float, float]
        ``(solar_rate_cents_per_kwh, alpha)``
    """
    alpha = calculate_alpha(usage_kwh, alpha_min, alpha_max, sensitivity)
    spread = grid_rate - export_rate
    solar_rate = export_rate + alpha * spread

    # Defensive clamping — ensures P_export ≤ P_solar ≤ P_grid
    solar_rate = max(export_rate, min(solar_rate, grid_rate))

    return solar_rate, alpha


# ═══════════════════════════════════════════════════════════════════════════
# Full interval calculation
# ═══════════════════════════════════════════════════════════════════════════


def calculate_interval_price(
    usage_kwh: float,
    solar_available_kwh: Optional[float],
    timestamp: datetime,
    pricing_mode: str,
    grid_rate_override: Optional[float] = None,
    export_rate_override: Optional[float] = None,
    fixed_solar_rate: float = 22.0,
    alpha_min: float = 0.40,
    alpha_max: float = 0.75,
    discount_sensitivity: float = 0.50,
) -> PricingResult:
    """
    Calculate the electricity charge for a single usage interval.

    This is the main entry-point for pricing logic.  It resolves tariffs,
    splits usage into solar / grid portions, computes the applicable rate,
    and returns a fully populated :class:`PricingResult`.

    Raises
    ------
    ValueError
        If the export rate exceeds the grid rate in dynamic mode.
    """

    # ── Resolve tariff rates ──────────────────────────────────────────────
    grid_rate = (
        grid_rate_override
        if grid_rate_override is not None
        else resolve_grid_rate(timestamp)
    )
    export_rate = (
        export_rate_override
        if export_rate_override is not None
        else resolve_export_rate(timestamp)
    )

    # ── Split usage into solar / grid portions ────────────────────────────
    if solar_available_kwh is not None:
        solar_usage = min(usage_kwh, solar_available_kwh)
        grid_usage = max(usage_kwh - solar_available_kwh, 0.0)
    else:
        # When solar_available_kwh is omitted, treat usage as solar directly
        solar_usage = usage_kwh
        grid_usage = 0.0

    # ── Determine solar rate ──────────────────────────────────────────────
    alpha: Optional[float]
    if pricing_mode == "fixed":
        solar_rate = fixed_solar_rate
        alpha = None
    else:
        # Dynamic mode — export rate must not exceed grid rate
        if export_rate > grid_rate:
            raise ValueError(
                "Export rate cannot exceed grid rate for dynamic tenant pricing."
            )
        solar_rate, alpha = calculate_dynamic_rate(
            solar_usage,
            grid_rate,
            export_rate,
            alpha_min,
            alpha_max,
            discount_sensitivity,
        )

    # ── Charges (dollars) ─────────────────────────────────────────────────
    solar_charge = cents_to_dollars(solar_usage * solar_rate)
    grid_charge = cents_to_dollars(grid_usage * grid_rate)
    total_charge = solar_charge + grid_charge

    # ── Tenant savings ────────────────────────────────────────────────────
    baseline_cost = cents_to_dollars(usage_kwh * grid_rate)
    tenant_saving = baseline_cost - total_charge
    tenant_saving_pct: Optional[float] = (
        round(tenant_saving / baseline_cost * 100, 2)
        if baseline_cost > 0
        else None
    )

    # ── Landlord benefit ──────────────────────────────────────────────────
    export_value = cents_to_dollars(solar_usage * export_rate)
    additional_revenue = solar_charge - export_value

    # ── Build result ──────────────────────────────────────────────────────
    return PricingResult(
        timestamp=timestamp,
        pricing_mode=pricing_mode,
        usage_kwh=round(usage_kwh, 4),
        solar_available_kwh=(
            round(solar_available_kwh, 4)
            if solar_available_kwh is not None
            else None
        ),
        solar_usage_kwh=round(solar_usage, 4),
        grid_usage_kwh=round(grid_usage, 4),
        grid_rate_cents_per_kwh=round(grid_rate, 4),
        export_rate_cents_per_kwh=round(export_rate, 4),
        alpha=round(alpha, 4) if alpha is not None else None,
        solar_rate_cents_per_kwh=round(solar_rate, 4),
        solar_charge_dollars=round(solar_charge, 4),
        grid_charge_dollars=round(grid_charge, 4),
        total_charge_dollars=round(total_charge, 4),
        tenant_grid_cost_without_solar_dollars=round(baseline_cost, 4),
        tenant_saving_dollars=round(tenant_saving, 4),
        tenant_saving_percentage=tenant_saving_pct,
        landlord_export_value_dollars=round(export_value, 4),
        landlord_additional_revenue_dollars=round(additional_revenue, 4),
    )
