"""Pure bounded sampling, percentile, and rank-correlation helpers."""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from .models import DistributionSummary

FloatArray: TypeAlias = NDArray[np.float64]


def sample_truncated_normal(
    rng: np.random.Generator,
    mean: float,
    std_dev: float,
    minimum: float,
    maximum: float | None = None,
    size: int | tuple[int, ...] | None = None,
) -> float | FloatArray:
    """Sample a normal distribution by rejection, preserving explicit bounds."""
    if std_dev < 0:
        raise ValueError("std_dev cannot be negative")
    if maximum is not None and minimum > maximum:
        raise ValueError("minimum cannot exceed maximum")

    if maximum is not None and minimum == maximum:
        if size is None:
            return float(minimum)
        return np.full(size, minimum, dtype=np.float64)

    if std_dev == 0:
        value = max(mean, minimum)
        if maximum is not None:
            value = min(value, maximum)
        if size is None:
            return float(value)
        return np.full(size, value, dtype=np.float64)

    samples = np.asarray(rng.normal(mean, std_dev, size=size), dtype=np.float64)
    scalar = samples.ndim == 0
    if scalar:
        samples = samples.reshape(1)

    def invalid_mask(values: FloatArray) -> NDArray[np.bool_]:
        invalid = values < minimum
        if maximum is not None:
            invalid |= values > maximum
        return invalid

    invalid = invalid_mask(samples)
    attempts = 0
    while np.any(invalid) and attempts < 10_000:
        samples[invalid] = rng.normal(
            mean, std_dev, size=int(np.count_nonzero(invalid))
        )
        invalid = invalid_mask(samples)
        attempts += 1
    if np.any(invalid):
        # Defensive termination for pathological bounds many standard deviations
        # from the mean. Normal request configurations should never reach this.
        samples = np.maximum(samples, minimum)
        if maximum is not None:
            samples = np.minimum(samples, maximum)

    return float(samples[0]) if scalar else samples


def sample_triangular(
    rng: np.random.Generator,
    minimum: float,
    mode: float,
    maximum: float,
    size: int | tuple[int, ...] | None = None,
) -> float | FloatArray:
    if not minimum <= mode <= maximum:
        raise ValueError("triangular values must satisfy minimum <= mode <= maximum")
    if minimum == maximum:
        if size is None:
            return float(minimum)
        return np.full(size, minimum, dtype=np.float64)
    sampled = rng.triangular(minimum, mode, maximum, size=size)
    return float(sampled) if size is None else np.asarray(sampled, dtype=np.float64)


def summarise_distribution(
    values: list[float] | FloatArray, decimal_places: int = 4
) -> DistributionSummary:
    array = np.asarray(values, dtype=np.float64)
    array = array[np.isfinite(array)]
    if array.size == 0:
        raise ValueError("cannot summarise an empty distribution")
    p05, p25, p50, p75, p95 = np.percentile(array, [5, 25, 50, 75, 95])
    rounded = lambda value: round(float(value), decimal_places)
    return DistributionSummary(
        mean=rounded(np.mean(array)),
        median=rounded(p50),
        std_dev=rounded(np.std(array)),
        p05=rounded(p05),
        p25=rounded(p25),
        p50=rounded(p50),
        p75=rounded(p75),
        p95=rounded(p95),
        minimum=rounded(np.min(array)),
        maximum=rounded(np.max(array)),
    )


def rank_values(values: FloatArray) -> FloatArray:
    """Return average one-based ranks, including correct handling of ties."""
    array = np.asarray(values, dtype=np.float64)
    _, inverse, counts = np.unique(array, return_inverse=True, return_counts=True)
    ends = np.cumsum(counts)
    starts = ends - counts
    average_ranks = (starts + ends - 1) / 2 + 1
    return np.asarray(average_ranks[inverse], dtype=np.float64)


def spearman_rank_correlation(first: FloatArray, second: FloatArray) -> float:
    first_array = np.asarray(first, dtype=np.float64)
    second_array = np.asarray(second, dtype=np.float64)
    mask = np.isfinite(first_array) & np.isfinite(second_array)
    if np.count_nonzero(mask) < 3:
        return 0.0
    first_ranks = rank_values(first_array[mask])
    second_ranks = rank_values(second_array[mask])
    if np.std(first_ranks) == 0 or np.std(second_ranks) == 0:
        return 0.0
    return float(np.corrcoef(first_ranks, second_ranks)[0, 1])
