"""A stock-flow model of the NYC rent freeze: vacancy and affordability.

QUESTION
--------
RGB Apartment & Loft Order #58 sets the renewal guideline for New York City's
~960,000 rent stabilized apartments to 0.0% for both one- and two-year leases,
for leases commencing 1 Oct 2026 - 30 Sep 2027. Relative to a counterfactual in
which the Board had set a positive guideline, how many additional apartments end
up vacant, and how many additional households end up priced out?

The two answers point in opposite directions, which is the whole difficulty. A
freeze mechanically lowers rent burdens for sitting tenants, so on the demand side
it keeps people housed. It also lowers the cash a landlord has to spend on a unit,
so on the supply side it pushes marginal apartments out of the rental stock and
marginal buildings into disrepair. The model exists to put magnitudes on both.

STATE AND DYNAMICS
------------------
A synthetic population of n units, each carrying

    rent_i      monthly collected rent
    cost_i      monthly operating & maintenance cost
    income_i    annual income of the sitting household (if occupied)
    deferred_i  accumulated dollars of skipped maintenance

evolved annually. The aggregate cross-section at t=0 is pinned to published
RGB/HVS statistics (`rent_freeze_data`); heterogeneity within the aggregate is
fitted, not posited.

    1. RENT. The rent roll grows by the lease-mix-weighted guideline

           g_hat_t = s1 * g1_t + (s2 / 2) * g2_t,     s1 = 0.424, s2 = 0.576

       since a one-year lease resets annually and, in steady state, half the
       two-year cohort resets in any given year. On vacancy an owner may reset a
       preferential rent to the registered legal rent; that channel survives a
       freeze and is applied at turnover.

    2. COST. Costs grow by the Price Index of Operating Costs, an AR(1) around the
       2017-2026 mean of 5.07%/yr, started at the RGB's own 2027 projection of
       4.1%. Costs are then reduced by the owner's maintenance response: as the
       operating margin falls, the discretionary share of the budget (maintenance
       plus administration, 30.1% of cost) is cut, and every dollar cut is booked
       to `deferred_i`. Deferred maintenance is the model's memory -- it is what
       turns a revenue squeeze today into a vacancy tomorrow.

    3. WAREHOUSING. Occupied units turn over at hazard tau. A vacated unit is
       returned to the market only if the owner can fund the work needed to make
       it rentable. The relevant constraint is cash, not net present value: the
       present value of a stabilized tenancy comfortably exceeds any plausible
       renovation invoice, yet 57,000 units sat empty in April 2025. What binds is
       that an owner whose building throws off little cash cannot raise the money,
       and since 2019 cannot recover it in rent either. So the model compares

           capacity_i = 12 * max(NOI_i, 0) * phi_IAI       (what can be funded)
           K_i        = K_med + deferred_i                  (what the job costs)

       where phi_IAI is how much of a dollar spent on the unit comes back as
       capitalised rent under the improvement rules. HSTPA is visible right here:
       recovery ran at 1/40th of cost per month before 2019, worth about $2.64 of
       capitalised rent per dollar spent, against 1/144th capped at $50,000 of
       spend today, worth about $0.73. Renovation used to pay for itself and now
       does not. The warehousing probability is

           logit p_w,i = a + b * ln( capacity_i / K_i )

       with `b` the semi-elasticity (see `hstpa_implied_slope` for where its range
       comes from) and `a` solved each run so the aggregate reproduces the
       observed April 2025 registered vacancy rate of 5.6%.

    4. HABITABILITY FAILURE. A unit whose deferred maintenance grows large
       relative to its rent fails at a hazard rising in deferred_i / (12 rent_i).
       Unlike warehousing this displaces a SITTING household, and it is the only
       supply-side channel in the model that prices anyone out.

    5. INCOME AND BURDEN. Incomes grow at unit-specific nominal rates drawn around
       the gradient the RGB measures across the distribution: 1.78%/yr at the
       bottom against 3.58%/yr at the top (2006-2023). Rent burden is
       b_i = 12 * rent_i / income_i, and a household is PRICED OUT when b_i crosses
       0.50 -- the standard severe-burden line, which the 2023 HVS measures
       directly for this population (27.2% of unassisted stabilized tenants), so
       the initial condition is observed rather than assumed.

IDENTIFICATION, AND ITS LIMITS
------------------------------
No rent freeze of this kind has been run before, so nothing here is estimated from
a freeze. The elasticity that matters -- how much warehousing responds to a cut in
a building's cash flow -- is anchored on the 2019 HSTPA episode, which cut exactly
that and was followed by registered stabilized vacancy rising from 3.7% to 5.6%.
Attributing the WHOLE of that rise to HSTPA gives a semi-elasticity of about 0.064
(percentage points of warehousing per log point of capacity); attributing half of
it gives 0.032. The Monte Carlo draws from [0.02, 0.08] and the result is reported
against that range rather than at a point, because this single number drives the
vacancy answer and it is not directly observed.

WHAT THE MODEL DOES NOT DO
--------------------------
It does not clear a market. Rents outside the stabilized stock are exogenous, so
the model cannot say what a freeze does to market-rate rents, to the queue of
households who want a stabilized unit and cannot get one, or to household
formation. Warehoused units are reported as units withdrawn from availability, NOT
as households displaced: nobody is evicted by an empty apartment. The displacement
figures count sitting households only. Net additions to the stabilized stock
(+21,281 in 2025, almost all new construction taking a tax benefit) are exogenous
to the RGB order and identical across scenarios, so they are excluded; they cancel
in every difference the model reports.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
from scipy import optimize, stats

import rent_freeze_data as D

__all__ = [
    "Params", "Policy", "freeze_policy", "counterfactual_policies",
    "fit_burden_distribution", "fit_cost_to_income_distribution",
    "fit_reaction_function", "hstpa_implied_slope", "calibrate_intercept",
    "build_cohort", "simulate", "monte_carlo", "compare", "summary",
    "START_YEAR", "HORIZON", "UNCERTAIN", "SEGMENTS",
]

START_YEAR = 2026        # guideline year beginning 1 Oct 2026 (Order #58)
HORIZON = 6              # guideline years simulated, 2026-27 through 2031-32


# ===========================================================================
# Policy paths
# ===========================================================================

@dataclass(frozen=True)
class Policy:
    """A guideline path: year -> (one-year %, two-year total % over the term)."""
    name: str
    schedule: dict[int, tuple[float, float]]

    def guideline(self, year: int) -> tuple[float, float]:
        return self.schedule.get(year, self.schedule[max(self.schedule)])

    def effective_growth(self, year: int) -> float:
        """Lease-mix-weighted rent-roll growth, in percent."""
        g1, g2 = self.guideline(year)
        return D.LEASE_MIX_ONE_YEAR * g1 + (D.LEASE_MIX_TWO_YEAR / 2.0) * g2


def freeze_policy(n_freeze_years: int = 3,
                  reversion: tuple[float, float] = (3.0, 5.2),
                  horizon: int = HORIZON) -> Policy:
    """0% for `n_freeze_years` guideline years, then `reversion`.

    Order #58 is one guideline year. The commitment that produced it was to freeze
    the rent across the mayoral term, so the base case carries three 0% orders and
    then returns to the recent-regime guideline. `n_freeze_years` is a scenario
    dial, not an estimate; `run_rent_freeze` sweeps it from 1 to 4.
    """
    return Policy(f"freeze{n_freeze_years}",
                  {START_YEAR + k: ((0.0, 0.0) if k < n_freeze_years else reversion)
                   for k in range(horizon)})


def counterfactual_policies(pioc: np.ndarray, horizon: int = HORIZON) -> dict[str, Policy]:
    """The three no-freeze guideline paths described in the module docstring."""
    ex_freeze = [y for y in range(2017, 2026) if y not in (2020, 2021)]
    low = (float(np.mean([D.GUIDELINES[y][1] for y in ex_freeze])),
           float(np.mean([D.GUIDELINES[y][2] for y in ex_freeze])))
    recent = list(range(2022, 2026))
    cen = (float(np.mean([D.GUIDELINES[y][1] for y in recent])),
           float(np.mean([D.GUIDELINES[y][2] for y in recent])))

    pols = {
        "low":     Policy("low",     {START_YEAR + k: low for k in range(horizon)}),
        "central": Policy("central", {START_YEAR + k: cen for k in range(horizon)}),
    }
    comm = {}
    for k in range(horizon):
        g1 = D.COST_TO_INCOME_RATIO * 100.0 * float(pioc[k])
        comm[START_YEAR + k] = (g1, 2.0 * g1)
    pols["commensurate"] = Policy("commensurate", comm)
    return pols


def fit_reaction_function(drop_freeze_years: bool = True) -> dict:
    """OLS of the one-year guideline on the contemporaneous PIOC change.

    Reported as a diagnostic, not used to build a counterfactual: dropping the
    years that were themselves freezes leaves essentially no relationship between
    the guideline and the cost index the Board is required to consider, which is
    precisely why the model runs three counterfactuals instead of one fitted rule.
    2026 is always excluded -- it is the treatment.
    """
    years = [y for y in range(2017, 2026)
             if not (drop_freeze_years and y in (2020, 2021))]
    x = np.array([D.PIOC_PCT_CHANGE[y] for y in years], float)
    y = np.array([D.GUIDELINES[y][1] for y in years], float)
    r = stats.linregress(x, y)
    return {"years": years, "n": len(years), "slope": float(r.slope),
            "intercept": float(r.intercept), "r2": float(r.rvalue ** 2),
            "p_value": float(r.pvalue), "slope_se": float(r.stderr)}


# ===========================================================================
# Cross-section fits
# ===========================================================================

def fit_burden_distribution(targets: dict | None = None) -> dict:
    """Fit LogNormal(mu, sigma) to the observed rent-burden cross-section.

    Three published targets, two free parameters, so the fit is falsifiable:
    median burden 27.0%, P(b > 0.30) = 45.5%, P(b > 0.50) = 27.2% among rent
    stabilized tenants without rental assistance (2023 HVS, via IA-2024).
    """
    t = targets or D.BURDEN_TARGETS

    def resid(theta):
        mu, sig = theta[0], math.exp(theta[1])
        return [math.exp(mu) - t["median"],
                1 - stats.norm.cdf((math.log(0.30) - mu) / sig) - t["p_over_30"],
                1 - stats.norm.cdf((math.log(0.50) - mu) / sig) - t["p_over_50"]]

    sol = optimize.least_squares(resid, x0=[math.log(0.27), math.log(0.95)])
    r = resid(sol.x)
    return {"mu": float(sol.x[0]), "sigma": float(math.exp(sol.x[1])),
            "median": float(math.exp(sol.x[0])),
            "resid_median": r[0], "resid_p30": r[1], "resid_p50": r[2],
            "max_abs_resid": float(np.max(np.abs(r)))}


def fit_cost_to_income_distribution() -> dict:
    """Fit LogNormal to the building-level operating-cost-to-income ratio.

    Pinned to two published facts: aggregate cost over aggregate income is 0.636
    (taken as the median of the building distribution), and 9.2% of buildings
    containing stabilized units reported costs exceeding income in 2024.
    """
    med = D.RPIE_2024["om_cost_unadjusted"] / D.RPIE_2024["total_income"]
    mu = math.log(med)
    sigma = -mu / stats.norm.ppf(1.0 - D.DISTRESSED_SHARE[2024] / 100.0)
    return {"mu": mu, "sigma": sigma, "median": med,
            "implied_mean": math.exp(mu + 0.5 * sigma ** 2),
            "implied_p_distress": float(1 - stats.norm.cdf(-mu / sigma))}


_BURDEN = fit_burden_distribution()      # fitted once; used in the hot loop


# Segment structure. Shares and relative positions are a coarse description of a
# stock the RGB reports by borough and building age. Absolute levels are
# renormalised in `build_cohort` so the weighted aggregate reproduces the published
# citywide rent and cost exactly, whatever the segment weights are.
SEGMENTS = [
    # name,                      share, rent multiple, cost/income median
    ("core_manhattan_mixed",     0.12,  1.95, 0.564),
    ("heavily_stabilized_pre74", 0.48,  0.79, 0.720),
    ("mixed_pre74_outer",        0.30,  0.98, 0.600),
    ("post_1973",                0.10,  1.25, 0.620),
]


# ===========================================================================
# Improvement-recovery leverage: the HSTPA channel
# ===========================================================================

def iai_leverage(divisor: float, spend_cap: float | None, annuity: float,
                 typical_job: float = 25_000.0) -> float:
    """Capitalised rent returned per dollar spent on a unit.

    A dollar of improvement spend buys 1/`divisor` dollars of monthly rent, worth
    `annuity` * 12 / divisor capitalised. Post-HSTPA the recoverable spend is
    capped, so on a job larger than the cap the average return is diluted.
    """
    eligible = typical_job if spend_cap is None else min(typical_job, spend_cap)
    return annuity * 12.0 * (eligible / divisor) / typical_job


def hstpa_implied_slope(p: "Params | None" = None) -> dict:
    """Where the warehousing semi-elasticity range comes from.

    Registered stabilized vacancy was 3.7% in 2016 and 5.6% in 2025. Netting off
    frictional vacancy and inverting the flow balance W = tau * p_w / omega turns
    those into warehousing probabilities. HSTPA changed improvement recovery from
    1/40th uncapped to 1/144th capped at $50,000, and removed the ~20% statutory
    vacancy allowance; together those move log capacity by a known amount. The
    ratio is the semi-elasticity IF the whole change is attributed to HSTPA, which
    is an upper bound -- the same period contains a pandemic and a Housing Court
    backlog.
    """
    p = p or Params()
    ann = annuity_factor(p)
    lev_post = iai_leverage(144.0, D.IAI_SPEND_CAP, ann)
    lev_pre = iai_leverage(40.0, None, ann)

    frict = p.turnover * p.frictional_months / 12.0
    pw = {}
    for yr, v in ((2016, D.STABILIZED_VACANCY_REGISTERED[2016] / 100.0),
                  (2025, D.STABILIZED_VACANCY_REGISTERED[2025] / 100.0)):
        pw[yr] = max(v - frict, 1e-4) * p.warehouse_exit / p.turnover

    # Capacity also moved with the ~20% vacancy allowance and with real NOI.
    d_ln_capacity = math.log(lev_pre / lev_post) + math.log(1.20)
    d_pw = pw[2025] - pw[2016]
    upper = d_pw / d_ln_capacity
    return {"leverage_post_2019": lev_post, "leverage_pre_2019": lev_pre,
            "p_warehouse_2016": pw[2016], "p_warehouse_2025": pw[2025],
            "d_ln_capacity": d_ln_capacity, "slope_if_all_hstpa": upper,
            "slope_if_half_hstpa": upper / 2.0}


# ===========================================================================
# Parameters
# ===========================================================================

@dataclass
class Params:
    """Assumptions and calibrated values. Measured quantities live in
    `rent_freeze_data`; anything here that is not a published figure is either
    swept in `UNCERTAIN` or solved for in `calibrate_intercept`."""

    n_units: float = float(D.STABILIZED_UNITS)
    n_sim: int = 80_000

    # --- cost process
    pioc_start: float = D.PIOC_PROJECTION_2027 / 100.0    # RGB's own 2027 forecast
    pioc_mean: float = D.mean_pioc() / 100.0              # 5.07%/yr, 2017-2026
    pioc_ar1: float = 0.35
    pioc_sd: float = 0.015

    # --- owner behaviour
    disc_share: float = D.DISCRETIONARY_COST_SHARE        # 0.301, maint + admin
    margin_target: float = 0.30       # operating margin below which cutting starts
    max_cut: float = 0.45             # most of the discretionary budget cuttable
    discount_rate: float = 0.07

    # --- turnover, warehousing
    turnover: float = 0.07            # annual hazard, occupied -> vacant
    frictional_months: float = 2.0    # off-market time for a unit that IS re-let
    makeready_median: float = 18_000.0
    warehouse_slope: float = 0.045    # dp_w / dln(capacity) at the fitted point
    warehouse_intercept: float = 0.0  # solved by calibrate_intercept
    logit_slope: float = 0.30         # derived from warehouse_slope, same place
    warehouse_exit: float = 0.30      # annual reconsideration rate, warehoused pool
    warehouse_writeoff: float = 0.07  # of those, share leaving the stock for good
    iai_divisor: float = 144.0        # $50,000 -> ~$347/month
    iai_cap: float | None = D.IAI_SPEND_CAP

    # --- preferential rents: recapture to legal rent on vacancy
    pref_rent_share: float = 0.30
    pref_rent_gap: float = D.LEGAL_VS_COLLECTED_GAP["citywide"] / 100.0

    # --- tenants
    income_growth_low: float = D.INCOME_CAGR_NOMINAL_LOWEST_QUINTILE / 100.0
    income_growth_high: float = D.INCOME_CAGR_NOMINAL_HIGHEST_QUINTILE / 100.0
    income_growth_sd: float = 0.030
    # Incoming tenants draw a burden from the fitted cross-section shifted by
    # `entrant_burden_shift` (in logs). The shift is solved, not assumed: because
    # heavily burdened households move out at a higher hazard, redrawing entrants
    # from the observed cross-section would deplete the upper tail and make severe
    # burden fall for no reason other than churn. The shift is set so that the
    # severe-burden share is STATIONARY when rents and incomes grow together,
    # which is the correct null for a policy comparison.
    # See calibrate_entrant_burden.
    entrant_burden_shift: float = 0.0
    new_tenant_income_premium: float = 0.05
    displacement_alpha: float = 0.25  # share of baseline moves that are
                                      # affordability-driven; sets the hazard slope
    burden_severe: float = 0.50
    burden_moderate: float = 0.30
    burden_cap: float = 3.0           # truncation for the hazard, not for counting

    # --- habitability failure
    fail_base: float = 0.0010
    fail_power: float = 1.5

    # --- roll-forward of the published cross-sections to 2026
    rollforward_yrs: int = 2
    rent_rollforward_rate: float = D.RPIE_2024_GROWTH["rental_income"] / 100.0
    cost_rollforward_rate: float = D.RPIE_2024_GROWTH["operating_cost"] / 100.0
    income_rollforward_yrs: int = 4                # 2022 HVS incomes -> 2026
    income_rollforward_rate: float = 0.050

    seed: int = 20260918


def annuity_factor(p: Params) -> float:
    """Present value of $1/yr over the expected tenancy 1/tau at rate r."""
    h, r = 1.0 / p.turnover, p.discount_rate
    return (1.0 - (1.0 + r) ** -h) / r


# ===========================================================================
# Cohort construction
# ===========================================================================

def build_cohort(p: Params, rng: np.random.Generator) -> dict:
    """Draw the t=0 cross-section of units, building finances and tenants."""
    n = p.n_sim
    sh = np.array([s[1] for s in SEGMENTS], float)
    sh = sh / sh.sum()
    seg = rng.choice(len(SEGMENTS), size=n, p=sh)

    rmul_all = np.array([s[2] for s in SEGMENTS], float)
    rent_mult = rmul_all[seg] / np.average(rmul_all, weights=sh)

    rent0 = (D.RPIE_2024["collected_rent"]
             * (1 + p.rent_rollforward_rate) ** p.rollforward_yrs)
    rent = rent0 * rent_mult * np.exp(rng.normal(-0.5 * 0.35 ** 2, 0.35, n))
    rent *= rent0 / rent.mean()                       # enforce the aggregate

    # Operating cost as a ratio to unit income. Two published facts must hold at
    # once and they are different statistics: AGGREGATE cost over AGGREGATE income
    # is 0.636, while 9.2% of BUILDINGS spend more than they take in. A single
    # lognormal cannot satisfy both unless the ratio is negatively correlated with
    # income, which it is -- expensive Manhattan stock runs a 0.564 ratio against
    # 0.72 in the heavily stabilized outer-borough stock. The segment structure
    # supplies that correlation; the location shift and spread below are solved so
    # that both facts hold exactly on the drawn cohort.
    ci = fit_cost_to_income_distribution()
    cmed_all = np.array([s[3] for s in SEGMENTS], float)
    base = np.log(cmed_all[seg]) - math.log(float(np.average(cmed_all, weights=sh)))
    z = rng.normal(0.0, 1.0, n)
    uplift = D.RPIE_2024["total_income"] / D.RPIE_2024["collected_rent"]
    income_unit = rent * uplift
    tgt_ratio = (D.RPIE_2024["om_cost_unadjusted"] / D.RPIE_2024["total_income"]
                 * (1 + p.cost_rollforward_rate) ** p.rollforward_yrs
                 / (1 + p.rent_rollforward_rate) ** p.rollforward_yrs)
    tgt_distress = D.DISTRESSED_SHARE[2024] / 100.0

    def _cost_resid(theta):
        c = np.exp(base + theta[0] + math.exp(theta[1]) * ci["sigma"] * z)
        agg = float((c * income_unit).sum() / income_unit.sum())
        return [agg - tgt_ratio, float((c > 1.0).mean()) - tgt_distress]

    sol = optimize.least_squares(_cost_resid, x0=[ci["mu"], 0.0])
    c_ratio = np.exp(base + sol.x[0] + math.exp(sol.x[1]) * ci["sigma"] * z)
    cost = c_ratio * income_unit

    burden = np.exp(rng.normal(_BURDEN["mu"], _BURDEN["sigma"], n))
    income = 12.0 * rent / burden
    inc0 = (D.HVS_2023_TENANTS["median_income_stabilized"]
            * (1 + p.income_rollforward_rate) ** p.income_rollforward_yrs)
    income *= inc0 / np.median(income)

    pct = stats.rankdata(income) / n
    inc_growth = (p.income_growth_low
                  + (p.income_growth_high - p.income_growth_low) * pct
                  + rng.normal(0.0, p.income_growth_sd, n))

    occupied = np.ones(n, bool)
    warehoused = np.zeros(n, bool)
    v0 = D.STABILIZED_VACANCY_REGISTERED[2025] / 100.0
    frict = p.turnover * p.frictional_months / 12.0
    idx = rng.choice(n, size=int(round(v0 * n)), replace=False)
    occupied[idx] = False
    warehoused[idx[int(round(frict * n)):]] = True    # the remainder is frictional

    # Observed RPIE cost is what owners ACTUALLY spent, which already embodies
    # whatever they were skipping in 2024. The requirement that generated it is
    # therefore higher: invert the cut rule for the implied `cost_req`, so that a
    # building whose margin does not change keeps spending the observed amount and
    # the distressed share runs on from the published figure instead of jumping.
    cost_req = cost.copy()
    for _ in range(25):
        m = (rent - cost_req) / np.maximum(rent, 1.0)
        cut0 = p.max_cut * np.clip((p.margin_target - m) / p.margin_target, 0.0, 1.0)
        cost_req = cost / np.maximum(1.0 - cut0 * p.disc_share, 0.5)

    return {"seg": seg, "rent": rent, "cost": cost, "cost_req": cost_req,
            "income": income, "inc_growth": inc_growth, "occupied": occupied,
            "warehoused": warehoused, "deferred": np.zeros(n),
            "alive": np.ones(n, bool), "weight": p.n_units / n}


def validate_cohort(p: Params | None = None, rng: np.random.Generator | None = None) -> dict:
    """Check the t=0 cross-section against the published statistics it targets."""
    p = p or Params()
    c = build_cohort(p, rng or np.random.default_rng(p.seed))
    uplift = D.RPIE_2024["total_income"] / D.RPIE_2024["collected_rent"]
    inc = c["rent"] * uplift
    b = 12 * c["rent"] / c["income"]
    roll_r = (1 + p.rent_rollforward_rate) ** p.rollforward_yrs
    roll_c = (1 + p.cost_rollforward_rate) ** p.rollforward_yrs
    roll_i = (1 + p.income_rollforward_rate) ** p.income_rollforward_yrs
    return {
        "mean rent ($/mo)":        (c["rent"].mean(), D.RPIE_2024["collected_rent"] * roll_r),
        "mean O&M cost ($/mo)":    (c["cost"].mean(), D.RPIE_2024["om_cost_unadjusted"] * roll_c),
        "mean NOI ($/mo)":         ((inc - c["cost"]).mean(), D.RPIE_2024["noi"] * roll_c),
        "cost / income (agg)":     (float((c["cost"].sum() / inc.sum())),
                                    D.RPIE_2024["om_cost_unadjusted"] / D.RPIE_2024["total_income"] * roll_c / roll_r),
        "distressed share (%)":    (100 * float((c["cost"] > inc).mean()), D.DISTRESSED_SHARE[2024]),
        "median tenant income ($)": (float(np.median(c["income"])),
                                     D.HVS_2023_TENANTS["median_income_stabilized"] * roll_i),
        "median rent burden (%)":  (100 * float(np.median(b)), 100 * D.BURDEN_TARGETS["median"]),
        "burdened >30% (%)":       (100 * float((b > 0.30).mean()), 100 * D.BURDEN_TARGETS["p_over_30"]),
        "severely burdened >50% (%)": (100 * float((b > 0.50).mean()), 100 * D.BURDEN_TARGETS["p_over_50"]),
        "registered vacancy (%)":  (100 * float((~c["occupied"]).mean()),
                                    D.STABILIZED_VACANCY_REGISTERED[2025]),
    }


# ===========================================================================
# The warehousing decision
# ===========================================================================

def _capacity(rent, cost, p: Params) -> np.ndarray:
    """Dollars an owner can mobilise for a unit, from its own annual cash flow,
    levered by whatever the improvement rules let them recover in rent."""
    uplift = D.RPIE_2024["total_income"] / D.RPIE_2024["collected_rent"]
    noi = rent * uplift - cost
    lev = iai_leverage(p.iai_divisor, p.iai_cap, annuity_factor(p))
    return 12.0 * np.maximum(noi, 0.0) * lev


def _warehouse_prob(rent, cost, deferred, p: Params) -> np.ndarray:
    """P(a newly vacant unit is NOT returned to the market)."""
    cap = _capacity(rent, cost, p)
    k = p.makeready_median + deferred
    # Cover ratio: how many times over the unit's own funding capacity covers the
    # job. Warehousing falls as the ratio rises, hence the negative sign --
    # `warehouse_slope` is dp_w / d(-ln cover) at the calibration point, converted
    # to a logit slope through dp/dx = b_logit * p * (1 - p).
    cover = np.log(np.maximum(cap, 1.0) / np.maximum(k, 1.0))
    return 1.0 / (1.0 + np.exp(-(p.warehouse_intercept - p.logit_slope * cover)))


def _target_pw(p: Params) -> float:
    """Warehousing probability implied by the observed 2025 registered vacancy.

    Registered vacancy = frictional + warehoused stock, and the warehoused stock is
    in flow balance at W / O = tau * p_w / omega.
    """
    v = D.STABILIZED_VACANCY_REGISTERED[2025] / 100.0
    frict = p.turnover * p.frictional_months / 12.0
    return float(np.clip((v - frict) * p.warehouse_exit / p.turnover, 1e-3, 0.95))


def calibrate_intercept(p: Params, rng: np.random.Generator,
                        cohort: dict | None = None, verbose: bool = False) -> Params:
    """Solve the logit intercept so the model reproduces April 2025 vacancy.

    The slope is supplied (drawn from the HSTPA-anchored range); only the level is
    fitted, and it is fitted to one published number.
    """
    c = cohort or build_cohort(replace(p, n_sim=min(p.n_sim, 20_000)), rng)
    tgt = _target_pw(p)
    b_logit = p.warehouse_slope / (tgt * (1.0 - tgt))
    q = replace(p, warehouse_intercept=0.0, logit_slope=b_logit)

    def resid(a):
        q.warehouse_intercept = float(a)
        return float(_warehouse_prob(c["rent"], c["cost"], c["deferred"], q).mean()) - tgt

    a = optimize.brentq(resid, -40.0, 40.0, xtol=1e-10)
    q.warehouse_intercept = float(a)
    if verbose:
        print(f"  target p_warehouse {tgt:.4f}  ->  intercept {a:+.4f}, "
              f"logit slope {b_logit:.4f}")
    return q


# ===========================================================================
# Simulation
# ===========================================================================

def calibrate_entrant_burden(p: Params, seed: int, cohort: dict,
                             horizon: int = HORIZON, verbose: bool = False) -> Params:
    """Solve the entrant-burden shift that makes severe burden stationary.

    Run the model on a NEUTRAL path -- rents and incomes growing at the same rate,
    no cost inflation, no preferential-rent recapture -- so the only thing that can
    move the severe-burden share is the churn of tenants through units. Under that
    path the share must be flat: a household replaced by another household at the
    same rent and the same income distribution changes nothing. Solving for the
    shift that delivers flatness removes an artefact that would otherwise make
    severe burden fall by a fifth over six years in every scenario, freeze or not.
    """
    g = 0.5 * (p.income_growth_low + p.income_growth_high) * 100.0
    neutral = Policy("neutral", {START_YEAR + k: (g, 2 * g) for k in range(horizon)})
    flat = np.zeros(horizon)
    q = replace(p, pref_rent_share=0.0)

    def resid(shift):
        r = simulate(neutral, replace(q, entrant_burden_shift=float(shift)),
                     np.random.default_rng(seed), horizon=horizon, pioc=flat,
                     cohort=cohort)
        return float(r["severely_burdened"][-1] - r["severely_burdened"][0])

    lo, hi = 0.0, 0.8
    f_lo, f_hi = resid(lo), resid(hi)
    tries = 0
    while f_lo * f_hi > 0 and tries < 6:        # widen if the root is outside
        hi += 0.5
        f_hi = resid(hi)
        tries += 1
    shift = optimize.brentq(resid, lo, hi, xtol=1e-4) if f_lo * f_hi <= 0 else hi
    if verbose:
        print(f"  entrant burden shift {shift:+.4f} in logs "
              f"(x{math.exp(shift):.3f} on the median entrant burden)")
    return replace(p, entrant_burden_shift=float(shift))


def pioc_path(p: Params, rng: np.random.Generator, horizon: int) -> np.ndarray:
    """AR(1) cost inflation, started at the RGB's published 2027 projection."""
    x = np.empty(horizon)
    x[0] = p.pioc_start
    for k in range(1, horizon):
        x[k] = (p.pioc_mean + p.pioc_ar1 * (x[k - 1] - p.pioc_mean)
                + rng.normal(0.0, p.pioc_sd))
    return np.clip(x, -0.02, 0.15)


_SERIES = ("year", "guideline", "pioc", "vacant_units", "vacancy_rate",
           "warehoused_units", "occupied_units", "severely_burdened", "burdened",
           "displaced_afford", "displaced_habitability", "units_lost",
           "mean_rent", "mean_cost", "mean_noi", "distressed_share",
           "median_burden", "deferred_per_unit", "stock")


def simulate(policy: Policy, p: Params, rng: np.random.Generator,
             horizon: int = HORIZON, pioc: np.ndarray | None = None,
             cohort: dict | None = None) -> dict:
    """Run one path. All count outputs are in real apartments / households."""
    st = {k: (v.copy() if isinstance(v, np.ndarray) else v)
          for k, v in (cohort if cohort is not None else build_cohort(p, rng)).items()}
    w = st["weight"]
    n = p.n_sim
    pioc = pioc_path(p, rng, horizon) if pioc is None else pioc
    uplift = D.RPIE_2024["total_income"] / D.RPIE_2024["collected_rent"]

    # Affordability hazard slope: set so that a share `displacement_alpha` of all
    # moves is affordability-driven at the t=0 burden cross-section.
    b0 = np.clip(12 * st["rent"] / st["income"], 0, p.burden_cap)
    ex0 = float(np.mean(np.maximum(b0 - p.burden_moderate, 0.0)))
    kappa = (p.displacement_alpha * p.turnover
             / max(ex0 * (1.0 - p.displacement_alpha), 1e-9))

    rec = {k: [] for k in _SERIES}
    cum_aff = cum_hab = cum_lost = 0.0

    for k in range(horizon):
        year = START_YEAR + k
        g = policy.effective_growth(year) / 100.0
        pi = float(pioc[k])
        alive = st["alive"]

        # --- 1. rents on occupied units
        np.multiply(st["rent"], 1 + g, out=st["rent"], where=st["occupied"] & alive)

        # --- 2. costs, then the owner's maintenance response.
        # `cost_req` is what the building needs spent on it and grows with the
        # price index unconditionally; `cost` is what actually gets spent. The cut
        # is a level reduction against the requirement, not a permanent reduction
        # in the requirement -- skipping maintenance this year does not make the
        # building cheaper to run next year, it makes it more expensive to re-let.
        np.multiply(st["cost_req"], 1 + pi, out=st["cost_req"], where=alive)
        margin = np.divide(st["rent"] - st["cost_req"], np.maximum(st["rent"], 1.0))
        cut = p.max_cut * np.clip((p.margin_target - margin) / p.margin_target, 0.0, 1.0)
        skipped = np.where(alive, cut * p.disc_share * st["cost_req"], 0.0)
        st["cost"] = st["cost_req"] - skipped
        st["deferred"] = st["deferred"] * (1 + pi) + 12.0 * skipped

        # --- 3. tenant incomes
        np.multiply(st["income"], 1 + st["inc_growth"], out=st["income"])

        occ = st["occupied"] & alive
        burden = np.where(occ, 12 * st["rent"] / np.maximum(st["income"], 1.0), np.nan)
        n_sev = int(np.nansum(burden > p.burden_severe))
        n_brd = int(np.nansum(burden > p.burden_moderate))

        # --- 4. habitability failure: displaces a sitting household
        rel = st["deferred"] / np.maximum(12 * st["rent"], 1.0)
        h_fail = np.clip(p.fail_base * (1 + rel) ** p.fail_power, 0.0, 0.25)
        fail = occ & (rng.random(n) < h_fail)

        # --- 5. turnover, raised by rent burden
        excess = np.maximum(np.clip(np.nan_to_num(burden), 0, p.burden_cap)
                            - p.burden_moderate, 0.0)
        h_move = np.clip(p.turnover + kappa * excess, 0.0, 0.6)
        moves = occ & ~fail & (rng.random(n) < h_move)
        aff_share = np.where(h_move > 0, kappa * excess / h_move, 0.0)

        cum_hab += int(fail.sum()) * w
        cum_aff += float((moves * aff_share).sum()) * w
        st["occupied"][fail | moves] = False

        # --- 6. re-let or warehouse the newly vacant
        pw = _warehouse_prob(st["rent"], st["cost"], st["deferred"], p)
        hold = moves & (rng.random(n) < pw)
        st["warehoused"] |= hold
        relet = moves & ~hold

        # --- 7. reconsider the standing warehoused stock
        review = st["warehoused"] & alive & (rng.random(n) < p.warehouse_exit)
        back = review & (rng.random(n) >= pw)
        writeoff = review & ~back & (rng.random(n) < p.warehouse_writeoff)
        st["warehoused"][back | writeoff] = False
        relet = relet | back

        # --- 8. units leaving the stock permanently
        dead = fail | writeoff
        cum_lost += int(dead.sum()) * w
        st["alive"][dead] = False
        st["occupied"][dead] = False
        st["warehoused"][dead] = False
        relet &= st["alive"]

        # --- 9. new tenants in re-let units, at the recaptured legal rent
        nre = int(relet.sum())
        if nre:
            st["rent"][relet] *= (1 + p.pref_rent_share * p.pref_rent_gap)
            st["deferred"][relet] = 0.0               # the work was paid for
            nb = np.exp(rng.normal(_BURDEN["mu"] + p.entrant_burden_shift,
                                   _BURDEN["sigma"], nre))
            st["income"][relet] = (12 * st["rent"][relet] / nb) * (
                1 + p.new_tenant_income_premium)
            st["occupied"][relet] = True

        alive = st["alive"]
        n_alive = int(alive.sum())
        occ = st["occupied"] & alive
        wh = st["warehoused"] & alive
        vacant = int(wh.sum()) + p.turnover * p.frictional_months / 12.0 * int(occ.sum())
        noi = np.where(alive, st["rent"] * uplift - st["cost"], np.nan)

        rec["year"].append(year)
        rec["guideline"].append(policy.guideline(year)[0])
        rec["pioc"].append(100 * pi)
        rec["stock"].append(n_alive * w)
        rec["vacant_units"].append(vacant * w)
        rec["vacancy_rate"].append(100 * vacant / max(n_alive, 1))
        rec["warehoused_units"].append(int(wh.sum()) * w)
        rec["occupied_units"].append(int(occ.sum()) * w)
        rec["severely_burdened"].append(n_sev * w)
        rec["burdened"].append(n_brd * w)
        rec["displaced_afford"].append(cum_aff)
        rec["displaced_habitability"].append(cum_hab)
        rec["units_lost"].append(cum_lost)
        rec["mean_rent"].append(float(np.nanmean(np.where(alive, st["rent"], np.nan))))
        rec["mean_cost"].append(float(np.nanmean(np.where(alive, st["cost"], np.nan))))
        rec["mean_noi"].append(float(np.nanmean(noi)))
        rec["distressed_share"].append(100 * float(np.mean(noi[alive] < 0)))
        rec["median_burden"].append(100 * float(np.nanmedian(burden)))
        rec["deferred_per_unit"].append(
            float(np.mean(st["deferred"][alive])) if n_alive else 0.0)

    return {k: np.asarray(v, float) for k, v in rec.items()}


# ===========================================================================
# Monte Carlo
# ===========================================================================

UNCERTAIN = {
    # name:                    (low, high) -- uniform, deliberately wide
    "turnover":                (0.050, 0.090),
    "max_cut":                 (0.250, 0.600),
    "margin_target":           (0.220, 0.380),
    "warehouse_exit":          (0.200, 0.450),
    "warehouse_slope":         (0.020, 0.080),   # anchored on the HSTPA episode
    "warehouse_writeoff":      (0.030, 0.120),
    "makeready_median":        (10_000.0, 30_000.0),
    "pref_rent_share":         (0.220, 0.380),
    "displacement_alpha":      (0.150, 0.350),
    "fail_base":               (0.0004, 0.0020),
    "income_growth_sd":        (0.020, 0.040),
    "pioc_mean":               (0.040, 0.060),
    "new_tenant_income_premium": (0.00, 0.20),
}


def monte_carlo(policies: dict[str, Policy], p: Params, n_draws: int = 400,
                horizon: int = HORIZON, seed: int | None = None,
                progress: bool = False) -> dict:
    """Run every policy on a COMMON set of parameter draws, cohorts and shocks.

    Pairing matters: the quantities of interest are differences between scenarios,
    and sharing the draws removes simulation noise that would otherwise swamp them.
    Each draw re-solves the warehousing intercept so the 2025 vacancy level is
    matched under every parameter combination.
    """
    root = np.random.default_rng(p.seed if seed is None else seed)
    out = {name: [] for name in policies}
    draws = []

    for d in range(n_draws):
        vals = {k: float(root.uniform(*v)) for k, v in UNCERTAIN.items()}
        draws.append(vals)
        q = replace(p, **vals)
        cseed = int(root.integers(1 << 62))
        cohort = build_cohort(q, np.random.default_rng(cseed))
        q = calibrate_intercept(q, np.random.default_rng(cseed), cohort=cohort)
        q = calibrate_entrant_burden(q, cseed, cohort, horizon)
        pi = pioc_path(q, np.random.default_rng(int(root.integers(1 << 62))), horizon)
        sseed = int(root.integers(1 << 62))
        for name, pol in policies.items():
            out[name].append(simulate(pol, q, np.random.default_rng(sseed),
                                      horizon=horizon, pioc=pi, cohort=cohort))
        if progress and (d + 1) % max(1, n_draws // 10) == 0:
            print(f"    draw {d + 1}/{n_draws}")

    res = {name: {k: np.stack([r[k] for r in runs]) for k in runs[0]}
           for name, runs in out.items()}
    res["_draws"] = {k: np.array([d[k] for d in draws]) for k in UNCERTAIN}
    return res


def compare(mc: dict, treated: str, control: str, key: str):
    """Paired difference (treated - control) for one series: median, p05, p95."""
    d = mc[treated][key] - mc[control][key]
    return np.median(d, 0), np.percentile(d, 5, 0), np.percentile(d, 95, 0)


def summary(mc: dict, name: str, key: str):
    a = mc[name][key]
    return np.median(a, 0), np.percentile(a, 5, 0), np.percentile(a, 95, 0)


if __name__ == "__main__":
    np.set_printoptions(precision=3, suppress=True)
    print("Rent-burden distribution fit (3 targets, 2 parameters):")
    for k, v in fit_burden_distribution().items():
        print(f"  {k:>16}: {v: .5f}")

    print("\nBuilding cost-to-income distribution fit:")
    for k, v in fit_cost_to_income_distribution().items():
        print(f"  {k:>20}: {v: .5f}")

    print("\nGuideline reaction function, PIOC -> one-year guideline:")
    for tag, drop in (("2017-2025 ex freeze years", True), ("2017-2025 all", False)):
        f = fit_reaction_function(drop)
        print(f"  {tag:>26}: n={f['n']}  slope={f['slope']:+.3f} "
              f"(se {f['slope_se']:.3f})  R2={f['r2']:.3f}  p={f['p_value']:.3f}")

    print("\nHSTPA-implied warehousing semi-elasticity:")
    for k, v in hstpa_implied_slope().items():
        print(f"  {k:>22}: {v: .4f}")

    p0 = Params(n_sim=40_000)
    rng = np.random.default_rng(0)
    coh = build_cohort(p0, rng)
    print("\nWarehousing intercept calibration:")
    p0 = calibrate_intercept(p0, rng, cohort=coh, verbose=True)
    print("Entrant-burden stationarity calibration:")
    calibrate_entrant_burden(p0, 0, coh, verbose=True)
