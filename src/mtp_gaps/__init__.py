"""Kalshi vs Polymarket price gaps: the threshold (band) model, its fit and its simulator."""

from .model import (
    BLOCK_MINUTES,
    C_GRID,
    CENTRE,
    MIN_BEYOND,
    STEP,
    TICK,
    block_stats,
    bootstrap_weights,
    calibrate,
    centre_values,
    excess,
    fit_c0,
    fit_from_weights,
    fit_threshold,
    half_life,
    make_pairs,
    sim_fit,
    sim_pairs,
    simulate,
    skill,
)

__version__ = "0.1.0"
