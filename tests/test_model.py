"""Tests of the band model against known mathematics (the c = 0 limit) and planted values."""

import numpy as np
import pytest

from mtp_gaps import (
    STEP,
    centre_values,
    excess,
    fit_c0,
    fit_threshold,
    half_life,
    make_pairs,
    simulate,
    skill,
)


def _pairs(series, step, centre="none"):
    minute = np.arange(len(series))
    dev = series - centre_values(minute, series, centre)
    return make_pairs(minute, dev, np.zeros(len(series), bool), step)


def test_excess_is_zero_inside_band_and_shifted_outside():
    g = np.array([-0.05, -0.01, 0.0, 0.01, 0.05])
    np.testing.assert_allclose(excess(g, 0.02), [-0.03, 0.0, 0.0, 0.0, 0.03])


def test_half_life_matches_formula():
    # kappa = 0.5 per 5-minute step: half the excess is gone after exactly one step
    assert half_life(0.5) == pytest.approx(STEP)
    k = 0.1
    assert half_life(k) == pytest.approx(STEP * np.log(2) / -np.log(1 - k))
    assert np.isnan(half_life(0.0))


def test_make_pairs_uses_only_rows_exactly_step_apart():
    minute = np.array([0, 1, 2, 5, 6, 10])
    dev = np.arange(6, dtype=float)
    p = make_pairs(minute, dev, np.zeros(6, bool), 5)
    # 0->5, 1->6, 5->10 are 5 minutes apart; 2->7 has no partner
    np.testing.assert_array_equal(p["minute"], [0, 1, 5])
    np.testing.assert_allclose(p["dg"], [3.0, 3.0, 2.0])


def test_c0_limit_reproduces_ar1_closed_forms():
    """With c = 0 the model is AR(1): the fit must return kappa, kappa_5 = 1-(1-kappa)^5 and the
    stationary spread sigma / sqrt(1-(1-kappa)^2)."""
    rng = np.random.default_rng(215)
    k_true, s_true, n = 0.05, 0.003, 20_000
    sims = simulate(np.arange(n), 0.0, k_true, s_true, 0.0, 0.0, 10, rng, tick=None)
    k1 = np.mean([fit_c0(_pairs(sims[:, j], 1)) for j in range(sims.shape[1])])
    k5 = np.mean([fit_c0(_pairs(sims[:, j], 5)) for j in range(sims.shape[1])])
    sd = np.mean(sims.std(axis=0))
    assert k1 == pytest.approx(k_true, rel=0.05)
    assert k5 == pytest.approx(1 - (1 - k_true) ** 5, rel=0.05)
    assert sd == pytest.approx(s_true / np.sqrt(1 - (1 - k_true) ** 2), rel=0.05)


def test_fit_recovers_a_planted_band():
    rng = np.random.default_rng(1)
    c_true, k5 = 0.02, 0.3
    k1 = 1 - (1 - k5) ** (1 / STEP)
    sims = simulate(np.arange(30_000), c_true, k1, 0.004, 0.0, 0.0, 3, rng, tick=None)
    c_hat = [fit_threshold(_pairs(sims[:, j], STEP, "median"))["c"] for j in range(3)]
    assert np.median(c_hat) == pytest.approx(c_true, abs=0.005)


def test_fit_does_not_invent_a_band():
    rng = np.random.default_rng(2)
    sims = simulate(np.arange(30_000), 0.0, 0.05, 0.003, 0.0, 0.0, 3, rng, tick=None)
    c_hat = [fit_threshold(_pairs(sims[:, j], STEP, "median"))["c"] for j in range(3)]
    assert max(c_hat) <= 0.003


def test_bootstrap_range_contains_the_estimate():
    rng = np.random.default_rng(3)
    k1 = 1 - (1 - 0.3) ** (1 / STEP)
    sim = simulate(np.arange(20_000), 0.01, k1, 0.004, 0.0, 0.0, 1, rng, tick=None)[:, 0]
    f = fit_threshold(_pairs(sim, STEP, "median"), n_boot=200, rng=rng)
    lo, hi = np.percentile(f["c_boot"], [2.5, 97.5])
    assert lo <= f["c"] <= hi


def test_skill_is_zero_for_the_baseline_and_positive_for_a_perfect_model():
    y = np.array([0.01, -0.02, 0.005])
    assert skill(y, np.zeros(3)) == pytest.approx(0.0)
    assert skill(y, y) == pytest.approx(100.0)
