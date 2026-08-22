import numpy as np
import pytest

from app.distributions import (
    sample_triangular,
    sample_truncated_normal,
    spearman_rank_correlation,
    summarise_distribution,
)


def test_truncated_normal_respects_bounds_and_is_reproducible() -> None:
    first = sample_truncated_normal(
        np.random.default_rng(42), 100, 40, 60, 130, size=5_000
    )
    second = sample_truncated_normal(
        np.random.default_rng(42), 100, 40, 60, 130, size=5_000
    )
    assert np.array_equal(first, second)
    assert np.min(first) >= 60
    assert np.max(first) <= 130


def test_truncated_normal_never_generates_negative_energy() -> None:
    samples = sample_truncated_normal(
        np.random.default_rng(7), 1_000, 900, 0, size=10_000
    )
    assert np.all(samples >= 0)


def test_triangular_respects_physical_limits() -> None:
    samples = sample_triangular(np.random.default_rng(3), 0.35, 0.55, 0.75, size=10_000)
    assert np.min(samples) >= 0.35
    assert np.max(samples) <= 0.75
    assert np.all((samples >= 0) & (samples <= 1))


def test_invalid_triangular_order_is_rejected() -> None:
    with pytest.raises(ValueError):
        sample_triangular(np.random.default_rng(1), 0.7, 0.5, 0.6)


def test_percentiles_are_ordered_and_include_mean_and_median() -> None:
    summary = summarise_distribution(np.arange(1, 101, dtype=float))
    assert summary.p05 <= summary.p25 <= summary.p50 <= summary.p75 <= summary.p95
    assert summary.mean == summary.median == 50.5


def test_spearman_detects_monotonic_direction() -> None:
    values = np.arange(20, dtype=float)
    assert spearman_rank_correlation(values, values) == pytest.approx(1)
    assert spearman_rank_correlation(values, values[::-1]) == pytest.approx(-1)
