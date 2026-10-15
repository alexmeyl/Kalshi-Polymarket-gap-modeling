"""Threshold ("band") model for the Kalshi - Polymarket price gap.

Model, with x_t the gap measured from its centre and a step of STEP minutes:

    x_{t+STEP} - x_t = -kappa * sign(x_t) * max(0, |x_t| - c) + noise

Inside the band |x| <= c nothing pulls the gap back; beyond it the excess shrinks by the
fraction kappa per step. With c = 0 this is ordinary mean reversion (AR(1)).

These functions were moved unchanged from notebook/fit_kappa.ipynb; the notebook imports them.
"""

import numpy as np
import pandas as pd

STEP = 5                                           # main time step (minutes)
CENTRE = "median"                                  # gaps measured from the market's median gap
C_GRID = np.round(np.arange(0, 0.1001, 0.001), 4)  # candidate c: 0 to 10 cents in 0.1-cent steps
MIN_BEYOND = 300                                   # a c needs at least this many pairs with |gap| > c
BLOCK_MINUTES = 60                                 # bootstrap block length (minutes)
TICK = 0.005                                       # half a cent: the smallest step in the gap


# ---------------------------------------------------------------------------------------------
# Centring and pairs
# ---------------------------------------------------------------------------------------------

def centre_values(minute, gap, how=CENTRE, train_until=None):
    """The level each gap is measured from.

    rolling24h: median of the gap over the previous 24 hours (only past data; the first hour, before
                there are 60 observations, uses the median of everything so far)
    median:     one median for the whole period (or for minutes <= train_until)
    none:       zero
    """
    if how == "none":
        return np.zeros(len(gap))
    if how == "median":
        src = gap if train_until is None else gap[minute <= train_until]
        return np.full(len(gap), float(np.median(src)))
    if how == "rolling24h":
        s = pd.Series(gap, index=pd.to_datetime(minute, unit="m"))
        roll = s.rolling("24h", min_periods=60).median()
        return roll.fillna(s.expanding().median()).to_numpy()
    raise ValueError(how)


def make_pairs(minute, dev, flagged, step):
    """Rows exactly `step` minutes apart, neither flagged. Returns start minute, gap, change."""
    pos = np.full(minute[-1] + step + 1, -1)
    pos[minute] = np.arange(len(minute))
    j = pos[minute + step]
    ok = j >= 0
    ok &= ~flagged & ~flagged[np.where(ok, j, 0)]
    i = np.flatnonzero(ok)
    j = j[ok]
    return {"minute": minute[i], "g0": dev[i], "dg": dev[j] - dev[i]}


# ---------------------------------------------------------------------------------------------
# The band and the fit
# ---------------------------------------------------------------------------------------------

def excess(g, c):
    """Part of the gap beyond the band: sign(g) * max(|g| - c, 0)."""
    return np.sign(g) * np.maximum(np.abs(g) - c, 0.0)


def block_stats(p, c_grid=C_GRID):
    """Per one-hour block and per candidate c: the sums the least-squares fit needs."""
    block = p["minute"] // BLOCK_MINUTES
    starts = np.flatnonzero(np.r_[True, block[1:] != block[:-1]])
    X = excess(p["g0"][:, None], c_grid[None, :])
    dg = p["dg"]
    return {"sxy": np.add.reduceat(X * dg[:, None], starts, axis=0),
            "sxx": np.add.reduceat(X * X, starts, axis=0),
            "cnt": np.add.reduceat((X != 0).astype(float), starts, axis=0),
            "syy": np.add.reduceat(dg * dg, starts)}


def fit_from_weights(st, w, c_grid=C_GRID):
    """Grid fit from block sums. w: block weights, shape (n_blocks,) or (n_draws, n_blocks)."""
    Sxy, Sxx, N, Syy = w @ st["sxy"], w @ st["sxx"], w @ st["cnt"], w @ st["syy"]
    explained = np.where(Sxx > 0, Sxy ** 2 / np.where(Sxx > 0, Sxx, 1.0), 0.0)
    sse = np.where(N >= MIN_BEYOND, Syy[..., None] - explained, np.inf)
    i = np.argmin(sse, axis=-1)
    take = lambda A: np.take_along_axis(A, np.asarray(i)[..., None], -1)[..., 0]
    with np.errstate(invalid="ignore", divide="ignore"):
        kappa = -take(Sxy) / take(Sxx)
        r2 = np.where(N >= MIN_BEYOND, explained / Syy[..., None], np.nan)
    return c_grid[i], kappa, r2, take(N)


def bootstrap_weights(n_blocks, n_draws, rng):
    """Block-bootstrap weights: how many times each block is drawn, for each resample."""
    return np.stack([np.bincount(rng.integers(0, n_blocks, n_blocks), minlength=n_blocks)
                     for _ in range(n_draws)]).astype(float)


def fit_threshold(p, n_boot=0, rng=None, c_grid=C_GRID):
    """Fit c (grid search) and kappa (least squares); optionally block-bootstrap both."""
    st = block_stats(p, c_grid)
    nb = len(st["syy"])
    c, k, r2, nbeyond = fit_from_weights(st, np.ones(nb), c_grid)
    out = {"c": float(c), "kappa": float(k), "r2_curve": r2, "n_beyond": int(nbeyond), "n_pairs": len(p["dg"])}
    if n_boot:
        cb, kb, _, _ = fit_from_weights(st, bootstrap_weights(nb, n_boot, rng), c_grid)
        out["c_boot"], out["kappa_boot"] = cb, kb
    return out


def fit_c0(p):
    """Plain mean reversion (c = 0): least-squares kappa through the origin."""
    g, dg = p["g0"], p["dg"]
    return -np.sum(g * dg) / np.sum(g * g)


def half_life(kappa, step=STEP):
    """Minutes for the excess beyond c to halve: step * ln 2 / -ln(1 - kappa).

    kappa >= 1 (all of it gone within one step) is clipped to 0.999 so it still plots;
    kappa <= 0 (no pull) gives NaN.
    """
    k = np.minimum(np.asarray(kappa, dtype=float), 0.999)
    with np.errstate(divide="ignore", invalid="ignore"):
        hl = step * np.log(0.5) / np.log(1 - k)
    return np.where(k > 0, hl, np.nan)


def skill(target, pred):
    """Prediction skill vs the random walk (predict no change), in %: 1 - MSE_model / MSE_RW."""
    target, pred = np.asarray(target, float), np.asarray(pred, float)
    return 100 * (1 - np.mean((target - pred) ** 2) / np.mean(target ** 2))


# ---------------------------------------------------------------------------------------------
# Simulation (used to verify the fit)
# ---------------------------------------------------------------------------------------------

def simulate(minute, c, k1, sigma, tau, stale, n_rep, rng, tick=TICK, burn=500):
    """Minute-by-minute threshold process, observed with flicker, rounding and stale quotes,
    kept only at the minutes present in `minute`. Returns array (len(minute), n_rep)."""
    n_total = minute[-1] + 1
    keep = np.zeros(n_total, bool)
    keep[minute] = True
    out = np.empty((len(minute), n_rep))
    L = np.zeros(n_rep)
    prev = np.zeros(n_rep)
    row = 0
    for t in range(-burn, n_total):
        L = L - k1 * excess(L, c) + sigma * rng.standard_normal(n_rep)
        obs = L + tau * rng.standard_normal(n_rep) if tau > 0 else L.copy()
        if tick:
            obs = np.round(obs / tick) * tick
        if stale > 0:
            obs = np.where(rng.random(n_rep) < stale, prev, obs)
        prev = obs
        if t >= 0 and keep[t]:
            out[row] = obs
            row += 1
    return out


def sim_pairs(minute, obs_col, step, centre=CENTRE):
    """Same treatment as the real data: measure from the centre, exact-step pairs."""
    dev = obs_col - centre_values(minute, obs_col, centre)
    return make_pairs(minute, dev, np.zeros(len(minute), bool), step)


def calibrate(minute, c, k1, tau, zero_share, var5, rng, n_iter=4, n_rep=10):
    """Tune the noise size sigma and the stale probability so the fake data match the real
    variance of 5-minute changes and the real share of unchanged minutes."""
    sigma, stale = np.sqrt(var5 / STEP), 0.0
    for _ in range(n_iter):
        trial = simulate(minute, c, k1, sigma, tau, stale, n_rep, rng)
        v5 = np.mean([np.var(sim_pairs(minute, trial[:, j], STEP)["dg"]) for j in range(n_rep)])
        z = np.mean([np.mean(np.abs(sim_pairs(minute, trial[:, j], 1)["dg"]) < 1e-9) for j in range(n_rep)])
        z_round = (z - stale) / (1 - stale)              # zeros that rounding alone produces
        stale = float(np.clip((zero_share - z_round) / (1 - z_round), 0.0, 0.98))
        sigma *= np.sqrt(var5 / v5)
    return sigma, stale


def sim_fit(minute, obs, step=STEP, n_boot=0, rng=None, c_grid=C_GRID, centre=CENTRE):
    """Fit every simulated column exactly like the real data."""
    return [fit_threshold(sim_pairs(minute, obs[:, r], step, centre), n_boot, rng, c_grid) for r in range(obs.shape[1])]
