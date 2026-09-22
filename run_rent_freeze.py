"""Run the NYC rent-freeze model: scenarios, Monte Carlo, figures, tables.

    python run_rent_freeze.py                 # full run, ~2 minutes
    python run_rent_freeze.py --draws 100     # quick
    python run_rent_freeze.py --no-figures

Writes figures to ./figures and a results table to ./RENT_FREEZE_RESULTS.md.

The headline comparison is a PAIRED difference: every scenario is run on the same
parameter draws, the same synthetic cohort and the same cost-inflation path, so
the reported effect is the policy and not the noise.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import replace

import numpy as np

import rent_freeze as M
import rent_freeze_data as D

FIGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "RENT_FREEZE_RESULTS.md")

# Reported scenarios. The freeze length is a scenario dial, not an estimate:
# Order #58 is one guideline year, the commitment behind it spans a mayoral term.
FREEZE_LENGTHS = (1, 2, 3, 4, 6)
BASE_FREEZE = 3
BASE_CONTROL = "central"


# ===========================================================================
# Reporting helpers
# ===========================================================================

def _fmt(x, unit=""):
    if abs(x) >= 1000:
        return f"{x:,.0f}{unit}"
    if abs(x) >= 10:
        return f"{x:,.1f}{unit}"
    return f"{x:,.2f}{unit}"


def band(med, lo, hi, unit="", k=-1):
    return f"{_fmt(med[k], unit)}  [{_fmt(lo[k], unit)}, {_fmt(hi[k], unit)}]"


def section(title, fh=None):
    line = "\n" + title + "\n" + "-" * len(title)
    print(line)
    if fh:
        fh.write(f"\n## {title}\n\n")


# ===========================================================================
# 1. The empirical setting
# ===========================================================================

def report_data(fh):
    section("1. The data: what a freeze is being applied to", fh)
    ys, pioc = D.pioc_series()
    cum_cost = np.prod([1 + v / 100 for v in pioc]) - 1
    gy, g1, g2 = D.guideline_series(2017, 2026)
    cum_rent = np.prod([1 + D.effective_guideline(y) / 100 for y in gy]) - 1

    rows = [
        ("Rent stabilized apartments", f"{D.STABILIZED_UNITS:,} (rent CONTROLLED, "
         f"a separate programme not covered by the order: {D.RENT_CONTROLLED_UNITS:,})"),
        ("Order #58 (1 Oct 2026 - 30 Sep 2027)", "0.0% one-year, 0.0% two-year, adopted 7-1"),
        ("Operating costs, cumulative 2017-2026 (PIOC)", f"+{100*cum_cost:.1f}%"),
        ("Rent roll, cumulative 2017-2026 (guidelines)", f"+{100*cum_rent:.1f}%"),
        ("Mean annual PIOC change 2017-2026", f"{D.mean_pioc():.2f}%"),
        ("Mean one-year guideline 2017-2026", f"{np.mean(g1):.2f}%"),
        ("RGB projection for the 2027 PIOC", f"+{D.PIOC_PROJECTION_2027:.1f}%"),
        ("Avg O&M cost per unit per month (2024 RPIE)",
         f"${D.RPIE_2024['om_cost_unadjusted']:,.0f} "
         f"(median ${D.RPIE_2024['om_cost_median']:,.0f})"),
        ("Avg collected rent per unit per month (2024)",
         f"${D.RPIE_2024['collected_rent']:,.0f}"),
        ("Avg net operating income per unit per month", f"${D.RPIE_2024['noi']:,.0f}"),
        ("Buildings spending more than they collect", f"{D.DISTRESSED_SHARE[2024]:.1f}% "
         f"(was {D.DISTRESSED_SHARE[2016]:.1f}% in 2016)"),
        ("Registered stabilized vacancy, April 2025",
         f"{D.STABILIZED_VACANCY_REGISTERED[2025]:.1f}% "
         f"({D.REGISTERED_VACANT_UNITS[2025]:,} units; "
         f"{D.STABILIZED_VACANCY_REGISTERED[2016]:.1f}% in 2016)"),
        ("Vacant AND available (2023 HVS)",
         f"{D.HVS_2023_VACANCY['rent_stabilized']:.2f}% stabilized, "
         f"{D.HVS_2023_VACANCY['citywide_net_rental']:.2f}% citywide"),
        ("Median stabilized tenant income (2022)",
         f"${D.HVS_2023_TENANTS['median_income_stabilized']:,.0f}"),
        ("Median stabilized contract rent (2023)",
         f"${D.HVS_2023_TENANTS['median_contract_rent_stabilized']:,.0f}"),
        ("Stabilized tenants rent burdened / severely",
         f"{D.HVS_2023_TENANTS['rent_burdened_stabilized']:.1f}% / "
         f"{D.HVS_2023_TENANTS['severely_burdened_stabilized']:.1f}%"),
        ("Median renter income growth 2024",
         f"+{D.INCOME_GROWTH_2024['median_renter_nominal']:.1f}% nominal, "
         f"+{D.INCOME_GROWTH_2024['median_renter_real']:.1f}% real"),
        ("Household income CAGR 2006-2023, nominal",
         f"{D.INCOME_CAGR_NOMINAL_LOWEST_QUINTILE:.2f}%/yr bottom quintile vs "
         f"{D.INCOME_CAGR_NOMINAL_HIGHEST_QUINTILE:.2f}%/yr top"),
    ]
    for k, v in rows:
        print(f"  {k:<46} {v}")
    fh.write("| Quantity | Value |\n|---|---|\n")
    for k, v in rows:
        fh.write(f"| {k} | {v} |\n")

    print(f"\n  Over 2017-2026 operating costs rose {100*cum_cost:.1f}% while the")
    print(f"  guideline-driven rent roll rose {100*cum_rent:.1f}%. The freeze starts")
    print("  from an already-compressed margin, not from a neutral one.")
    fh.write(f"\nOver 2017-2026 operating costs rose **{100*cum_cost:.1f}%** while the "
             f"guideline-driven rent roll rose **{100*cum_rent:.1f}%**. The freeze "
             "starts from an already-compressed margin.\n")
    return ys, pioc, gy, g1


def report_calibration(fh):
    section("2. Calibration and identification", fh)
    b = M.fit_burden_distribution()
    c = M.fit_cost_to_income_distribution()
    rf_ex = M.fit_reaction_function(True)
    rf_all = M.fit_reaction_function(False)
    h = M.hstpa_implied_slope()
    v = M.validate_cohort(M.Params(n_sim=60_000))

    print(f"  Rent-burden lognormal: median {b['median']:.3f}, sigma {b['sigma']:.3f}; "
          f"worst residual against 3 published targets {b['max_abs_resid']:.4f}")
    print(f"  Cost/income lognormal: median {c['median']:.3f}, sigma {c['sigma']:.3f}")
    print(f"  Guideline on PIOC, 2017-2025 all years:      slope {rf_all['slope']:+.3f} "
          f"(se {rf_all['slope_se']:.3f}), R2 {rf_all['r2']:.3f}, p {rf_all['p_value']:.2f}")
    print(f"  Guideline on PIOC, excluding freeze years:   slope {rf_ex['slope']:+.3f} "
          f"(se {rf_ex['slope_se']:.3f}), R2 {rf_ex['r2']:.3f}, p {rf_ex['p_value']:.2f}")
    print("    -> the Board's guideline does not track its own cost index, so the")
    print("       counterfactual is a range of three policies, not a fitted rule.")
    print(f"  Improvement recovery per $1 spent: ${h['leverage_pre_2019']:.2f} before "
          f"HSTPA, ${h['leverage_post_2019']:.2f} after")
    print(f"  Warehousing semi-elasticity implied by 2016->2025: "
          f"{h['slope_if_all_hstpa']:.3f} (all of it) to "
          f"{h['slope_if_half_hstpa']:.3f} (half of it); "
          f"swept over {M.UNCERTAIN['warehouse_slope']}")

    print("\n  t=0 cross-section against its published targets:")
    for k, (got, tgt) in v.items():
        print(f"    {k:<30} {got:>12,.2f}   target {tgt:>12,.2f}")

    fh.write(f"- Rent-burden lognormal fitted to three published targets "
             f"(median 27.0%, P(>30%)=45.5%, P(>50%)=27.2%); worst residual "
             f"{b['max_abs_resid']:.4f}.\n")
    fh.write(f"- Guideline-on-PIOC regression: slope {rf_all['slope']:+.3f} "
             f"(R2 {rf_all['r2']:.3f}) on all years, {rf_ex['slope']:+.3f} "
             f"(R2 {rf_ex['r2']:.3f}, p={rf_ex['p_value']:.2f}) excluding freeze "
             "years. The Board's guideline is not a function of its cost index, "
             "so three counterfactuals are carried rather than one fitted rule.\n")
    fh.write(f"- Improvement recovery fell from ${h['leverage_pre_2019']:.2f} to "
             f"${h['leverage_post_2019']:.2f} of capitalised rent per dollar spent "
             "at HSTPA (2019). That episode anchors the warehousing "
             f"semi-elasticity at {h['slope_if_half_hstpa']:.3f}-"
             f"{h['slope_if_all_hstpa']:.3f}; the Monte Carlo sweeps "
             f"{M.UNCERTAIN['warehouse_slope']}.\n\n")
    fh.write("| t=0 cross-section | model | published target |\n|---|---|---|\n")
    for k, (got, tgt) in v.items():
        fh.write(f"| {k} | {got:,.2f} | {tgt:,.2f} |\n")
    return h


# ===========================================================================
# 2. Main Monte Carlo
# ===========================================================================

def run_mc(draws: int, horizon: int, n_sim: int, progress: bool):
    p = M.Params(n_sim=n_sim)
    pi_nom = M.pioc_path(p, np.random.default_rng(p.seed), horizon)
    pols = {f"freeze{k}": M.freeze_policy(k, horizon=horizon) for k in FREEZE_LENGTHS}
    pols.update(M.counterfactual_policies(pi_nom, horizon=horizon))
    print(f"\n  running {len(pols)} scenarios x {draws} draws x {n_sim:,} units ...")
    mc = M.monte_carlo(pols, p, n_draws=draws, horizon=horizon, progress=progress)
    return p, pols, mc


def report_headline(mc, fh, horizon):
    years = np.arange(M.START_YEAR, M.START_YEAR + horizon)
    treat = f"freeze{BASE_FREEZE}"

    section(f"3. Headline: {BASE_FREEZE}-year freeze vs the '{BASE_CONTROL}' "
            f"counterfactual", fh)
    print("  Paired differences, median [5th, 95th percentile] across draws.")
    print(f"  Cumulative through guideline year {years[-1]}-{str(years[-1]+1)[2:]}.\n")

    keys = [
        ("vacant_units",           "Vacant stabilized apartments (stock)", ""),
        ("vacancy_rate",           "Registered vacancy rate", " pp"),
        ("warehoused_units",       "  of which warehoused (off market)", ""),
        ("severely_burdened",      "Households paying >50% of income in rent", ""),
        ("burdened",               "Households paying >30% of income in rent", ""),
        ("displaced_afford",       "Cumulative affordability-driven moves", ""),
        ("displaced_habitability", "Cumulative displacements, habitability failure", ""),
        ("units_lost",             "Cumulative apartments lost from the stock", ""),
        ("mean_noi",               "Mean net operating income, $/unit/month", ""),
        ("distressed_share",       "Buildings spending more than they collect", " pp"),
        ("deferred_per_unit",      "Deferred maintenance, $/unit", ""),
    ]
    fh.write(f"Paired differences ({BASE_FREEZE}-year freeze minus "
             f"'{BASE_CONTROL}'), median [5th, 95th pct], at "
             f"{years[-1]}-{str(years[-1]+1)[2:]}:\n\n")
    fh.write("| Quantity | Difference at horizon | Peak year | Peak difference |\n")
    fh.write("|---|---|---|---|\n")
    for key, label, unit in keys:
        med, lo, hi = M.compare(mc, treat, BASE_CONTROL, key)
        j = int(np.argmax(np.abs(med)))
        print(f"  {label:<48} {band(med, lo, hi, unit):>34}")
        fh.write(f"| {label} | {band(med, lo, hi, unit)} | {years[j]} | "
                 f"{_fmt(med[j], unit)} |\n")

    # The net affordability question.
    sev_med, sev_lo, sev_hi = M.compare(mc, treat, BASE_CONTROL, "severely_burdened")
    aff_med, aff_lo, aff_hi = M.compare(mc, treat, BASE_CONTROL, "displaced_afford")
    hab_med, hab_lo, hab_hi = M.compare(mc, treat, BASE_CONTROL, "displaced_habitability")
    net_med = -aff_med - hab_med          # positive = freeze keeps more people housed
    net_lo = -aff_hi - hab_hi
    net_hi = -aff_lo - hab_lo

    print("\n  Net effect on households (positive = the freeze keeps people housed):")
    print(f"    demand side, affordability moves avoided   {_fmt(-aff_med[-1])}")
    print(f"    supply side, habitability displacements    {_fmt(-hab_med[-1])}")
    print(f"    NET households kept in their homes         "
          f"{_fmt(net_med[-1])}  [{_fmt(net_lo[-1])}, {_fmt(net_hi[-1])}]")
    fh.write(f"\n**Net effect on sitting households** at the horizon: the freeze "
             f"avoids {_fmt(-aff_med[-1])} affordability-driven moves and causes "
             f"{_fmt(hab_med[-1])} additional displacements through habitability "
             f"failure, for a net {_fmt(net_med[-1])} households "
             f"[{_fmt(net_lo[-1])}, {_fmt(net_hi[-1])}] who stay put.\n")
    return net_med, net_lo, net_hi


def report_counterfactual_spread(mc, fh, horizon):
    section("4. How much the answer depends on the counterfactual", fh)
    treat = f"freeze{BASE_FREEZE}"
    fh.write("| Counterfactual | 1-yr guideline | Extra vacant units | "
             "Fewer severely burdened |\n|---|---|---|---|\n")
    print(f"  {'counterfactual':<16}{'extra vacant units':>26}"
          f"{'fewer severely burdened':>30}")
    for ctrl in ("low", "central", "commensurate"):
        vm, vl, vh = M.compare(mc, treat, ctrl, "vacant_units")
        sm, sl, sh = M.compare(mc, treat, ctrl, "severely_burdened")
        print(f"  {ctrl:<16}{band(vm, vl, vh):>26}{band(-sm, -sh, -sl):>30}")
        g = mc[ctrl]["guideline"][0].mean() if ctrl != "commensurate" else float(
            np.mean(mc[ctrl]["guideline"]))
        fh.write(f"| {ctrl} | {g:.2f}% | {band(vm, vl, vh)} | "
                 f"{band(-sm, -sh, -sl)} |\n")


def report_duration_sweep(mc, fh, horizon):
    section("5. Effect of freeze duration", fh)
    print(f"  {'freeze length':<16}{'extra vacant units':>26}"
          f"{'fewer severely burdened':>30}{'extra units lost':>22}")
    fh.write("| Freeze length | Extra vacant units | Fewer severely burdened | "
             "Extra apartments lost |\n|---|---|---|---|\n")
    rows = []
    for k in FREEZE_LENGTHS:
        t = f"freeze{k}"
        vm, vl, vh = M.compare(mc, t, BASE_CONTROL, "vacant_units")
        sm, sl, sh = M.compare(mc, t, BASE_CONTROL, "severely_burdened")
        lm, ll, lh = M.compare(mc, t, BASE_CONTROL, "units_lost")
        label = f"{k} year" + ("s" if k > 1 else "") + (" (whole horizon)" if k >= horizon else "")
        print(f"  {label:<16}{band(vm, vl, vh):>26}{band(-sm, -sh, -sl):>30}"
              f"{band(lm, ll, lh):>22}")
        fh.write(f"| {label} | {band(vm, vl, vh)} | {band(-sm, -sh, -sl)} | "
                 f"{band(lm, ll, lh)} |\n")
        rows.append((k, vm[-1], -sm[-1], lm[-1]))
    return rows


def report_sensitivity(mc, fh, horizon):
    section("6. What the answer is sensitive to", fh)
    treat = f"freeze{BASE_FREEZE}"
    dv = (mc[treat]["vacant_units"] - mc[BASE_CONTROL]["vacant_units"])[:, -1]
    ds = -(mc[treat]["severely_burdened"] - mc[BASE_CONTROL]["severely_burdened"])[:, -1]
    draws = mc["_draws"]

    print(f"  Rank correlation of each parameter with the outcome (n={len(dv)} draws)")
    print(f"  {'parameter':<28}{'extra vacant':>16}{'fewer burdened':>18}")
    fh.write(f"Spearman rank correlation between each swept parameter and the "
             f"outcome, across {len(dv)} draws:\n\n")
    fh.write("| Parameter | corr with extra vacant units | "
             "corr with fewer severely burdened |\n|---|---|---|\n")
    from scipy import stats as sps
    rows = []
    for k, v in draws.items():
        a = sps.spearmanr(v, dv).statistic
        b = sps.spearmanr(v, ds).statistic
        rows.append((k, a, b))
    rows.sort(key=lambda r: -abs(r[1]))
    for k, a, b in rows:
        print(f"  {k:<28}{a:>16.3f}{b:>18.3f}")
        fh.write(f"| `{k}` | {a:+.3f} | {b:+.3f} |\n")
    return rows, dv, ds


# ===========================================================================
# 3. Figures
# ===========================================================================

def make_figures(mc, horizon, data_bits):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(FIGDIR, exist_ok=True)
    years = np.arange(M.START_YEAR, M.START_YEAR + horizon)
    treat = f"freeze{BASE_FREEZE}"
    ys, pioc, gy, g1 = data_bits
    C = {"freeze1": "#e59866", "freeze2": "#d98880", "freeze3": "#c0392b",
         "freeze4": "#922b21", "freeze6": "#5b1a13", "central": "#2471a3",
         "low": "#5dade2", "commensurate": "#148f77"}

    # --- fig 1: costs against guidelines -----------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].bar(np.array(ys) - 0.2, pioc, 0.4, label="operating costs (PIOC)",
              color="#c0392b")
    ax[0].bar(np.array(gy) + 0.2, [D.effective_guideline(y) for y in gy], 0.4,
              label="rent roll (lease-mix guideline)", color="#2471a3")
    ax[0].set_ylabel("% change"); ax[0].set_title("Annual change")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=.3, axis="y")
    cc = np.cumprod([1 + v / 100 for v in pioc])
    cg = np.cumprod([1 + D.effective_guideline(y) / 100 for y in gy])
    ax[1].plot(ys, 100 * (cc - 1), "o-", color="#c0392b", label="operating costs")
    ax[1].plot(gy, 100 * (cg - 1), "s-", color="#2471a3", label="rent roll")
    ax[1].fill_between(ys, 100 * (cg - 1), 100 * (cc - 1), color="#c0392b", alpha=.12)
    ax[1].set_ylabel("cumulative % since 2016"); ax[1].set_title("Cumulative")
    ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
    for a in ax:
        a.axvline(2025.5, color="k", ls=":", lw=1)
        a.annotate("Order #58\nfreeze", (2026, a.get_ylim()[1] * .82), fontsize=7,
                   ha="center", color="#7b241c")
    fig.suptitle("What the freeze is applied to: NYC rent stabilized stock, 2017-2026",
                 fontsize=11)
    fig.tight_layout(); fig.savefig(f"{FIGDIR}/fig_rf1_costs_vs_guidelines.png", dpi=150)
    plt.close(fig)

    # --- fig 2: vacancy ----------------------------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    hy = sorted(D.STABILIZED_VACANCY_REGISTERED)
    ax[0].plot(hy, [D.STABILIZED_VACANCY_REGISTERED[y] for y in hy], "ko--",
               label="observed (HCR registrations, 1 April)")
    for name in ("freeze3", "freeze6", "central", "commensurate"):
        m, lo, hi = M.summary(mc, name, "vacancy_rate")
        ax[0].plot(years, m, "-", color=C[name], label=name)
        ax[0].fill_between(years, lo, hi, color=C[name], alpha=.12)
    ax[0].axhline(5, color="gray", ls=":", lw=1)
    ax[0].annotate("5% statutory threshold", (2017, 5.08), fontsize=7, color="gray")
    ax[0].set_ylabel("registered vacancy rate (%)")
    ax[0].set_title("Stabilized vacancy: history and projection")
    ax[0].legend(fontsize=7); ax[0].grid(alpha=.3)

    for name in ("freeze1", "freeze3", "freeze6"):
        m, lo, hi = M.compare(mc, name, BASE_CONTROL, "vacant_units")
        ax[1].plot(years, m, "-", color=C[name], label=name)
        ax[1].fill_between(years, lo, hi, alpha=.12, color=C[name])
    ax[1].axhline(0, color="k", lw=.8)
    ax[1].set_ylabel(f"extra vacant apartments vs '{BASE_CONTROL}'")
    ax[1].set_title("Additional vacancy attributable to the freeze")
    ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(f"{FIGDIR}/fig_rf2_vacancy.png", dpi=150)
    plt.close(fig)

    # --- fig 3: affordability ---------------------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    for name in ("freeze3", "freeze6", "central", "commensurate"):
        m, lo, hi = M.summary(mc, name, "severely_burdened")
        ax[0].plot(years, m / 1000, "-", color=C[name], label=name)
        ax[0].fill_between(years, lo / 1000, hi / 1000, color=C[name], alpha=.12)
    ax[0].set_ylabel("households paying >50% of income in rent (000s)")
    ax[0].set_title("Severe rent burden among stabilized tenants")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)

    aff, al, ah = M.compare(mc, treat, BASE_CONTROL, "displaced_afford")
    hab, hl, hh = M.compare(mc, treat, BASE_CONTROL, "displaced_habitability")
    ax[1].bar(years - 0.2, -aff, 0.4, color="#2471a3",
              label="affordability moves avoided (demand side)")
    ax[1].bar(years + 0.2, -hab, 0.4, color="#c0392b",
              label="displaced by habitability failure (supply side)")
    ax[1].plot(years, -aff - hab, "ko-", lw=1.5, ms=4, label="net households kept housed")
    ax[1].axhline(0, color="k", lw=.8)
    ax[1].set_ylabel(f"households vs '{BASE_CONTROL}' (cumulative)")
    ax[1].set_title(f"Two channels, {BASE_FREEZE}-year freeze")
    ax[1].legend(fontsize=7); ax[1].grid(alpha=.3, axis="y")
    fig.tight_layout(); fig.savefig(f"{FIGDIR}/fig_rf3_affordability.png", dpi=150)
    plt.close(fig)

    # --- fig 4: the trade-off ----------------------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    xs, ys_, es = [], [], []
    for k in FREEZE_LENGTHS:
        vm, vl, vh = M.compare(mc, f"freeze{k}", BASE_CONTROL, "vacant_units")
        sm, sl, sh = M.compare(mc, f"freeze{k}", BASE_CONTROL, "severely_burdened")
        xs.append(vm[-1]); ys_.append(-sm[-1]); es.append(k)
    ax[0].plot(xs, ys_, "o-", color="#7b241c")
    for x, y, k in zip(xs, ys_, es):
        ax[0].annotate(f"{k}yr", (x, y), textcoords="offset points",
                       xytext=(6, 4), fontsize=8)
    ax[0].set_xlabel("extra vacant apartments"); ax[0].set_ylabel(
        "fewer severely rent-burdened households")
    ax[0].set_title("The trade-off, by freeze duration")
    ax[0].grid(alpha=.3)

    dv = (mc[treat]["vacant_units"] - mc[BASE_CONTROL]["vacant_units"])[:, -1]
    ds = -(mc[treat]["severely_burdened"]
           - mc[BASE_CONTROL]["severely_burdened"])[:, -1]
    sc = ax[1].scatter(dv, ds, c=mc["_draws"]["warehouse_slope"], s=10,
                       cmap="viridis")
    plt.colorbar(sc, ax=ax[1], label="warehousing semi-elasticity")
    ax[1].axvline(0, color="k", lw=.8); ax[1].axhline(0, color="k", lw=.8)
    ax[1].set_xlabel("extra vacant apartments")
    ax[1].set_ylabel("fewer severely rent-burdened households")
    ax[1].set_title(f"Parameter uncertainty ({len(dv)} draws), {BASE_FREEZE}-yr freeze")
    ax[1].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(f"{FIGDIR}/fig_rf4_tradeoff.png", dpi=150)
    plt.close(fig)

    # --- fig 5: landlord finances -----------------------------------------
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    for key, a, lab in (("mean_noi", ax[0], "net operating income ($/unit/mo)"),
                        ("distressed_share", ax[1], "buildings spending > income (%)"),
                        ("deferred_per_unit", ax[2], "deferred maintenance ($/unit)")):
        for name in ("freeze3", "freeze6", "central", "commensurate"):
            m, lo, hi = M.summary(mc, name, key)
            a.plot(years, m, "-", color=C[name], label=name)
            a.fill_between(years, lo, hi, color=C[name], alpha=.12)
        a.set_ylabel(lab); a.grid(alpha=.3)
    ax[1].axhline(D.DISTRESSED_SHARE[2024], color="k", ls=":", lw=1)
    ax[1].annotate("2024 actual", (years[0], D.DISTRESSED_SHARE[2024] + .15), fontsize=7)
    ax[0].legend(fontsize=7)
    fig.suptitle("Owner finances: the channel through which a freeze reaches vacancy",
                 fontsize=11)
    fig.tight_layout(); fig.savefig(f"{FIGDIR}/fig_rf5_owner_finance.png", dpi=150)
    plt.close(fig)

    # --- fig 6: sensitivity tornado ---------------------------------------
    from scipy import stats as sps
    names, corr = [], []
    for k, v in mc["_draws"].items():
        names.append(k); corr.append(sps.spearmanr(v, dv).statistic)
    order = np.argsort(np.abs(corr))
    fig, axx = plt.subplots(figsize=(7, 4.6))
    axx.barh([names[i] for i in order], [corr[i] for i in order],
             color=["#c0392b" if corr[i] > 0 else "#2471a3" for i in order])
    axx.axvline(0, color="k", lw=.8)
    axx.set_xlabel("Spearman correlation with extra vacant apartments")
    axx.set_title(f"What drives the vacancy answer ({BASE_FREEZE}-year freeze)")
    axx.grid(alpha=.3, axis="x")
    fig.tight_layout(); fig.savefig(f"{FIGDIR}/fig_rf6_sensitivity.png", dpi=150)
    plt.close(fig)

    print(f"\n  figures written to {FIGDIR}")


# ===========================================================================
# main
# ===========================================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=400)
    ap.add_argument("--horizon", type=int, default=M.HORIZON)
    ap.add_argument("--units", type=int, default=80_000)
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--progress", action="store_true")
    a = ap.parse_args()

    with open(RESULTS, "w", encoding="utf-8") as fh:
        fh.write("# NYC rent freeze: model results\n\n")
        fh.write(f"Generated by `run_rent_freeze.py` with {a.draws} Monte Carlo "
                 f"draws, {a.units:,} synthetic units, {a.horizon} guideline years "
                 f"from {M.START_YEAR}.\n")
        fh.write("All intervals are 5th-95th percentiles across parameter draws. "
                 "Scenario comparisons are paired: every scenario sees the same "
                 "cohort, parameters and cost-inflation path.\n")

        data_bits = report_data(fh)
        report_calibration(fh)
        p, pols, mc = run_mc(a.draws, a.horizon, a.units, a.progress)
        report_headline(mc, fh, a.horizon)
        report_counterfactual_spread(mc, fh, a.horizon)
        report_duration_sweep(mc, fh, a.horizon)
        report_sensitivity(mc, fh, a.horizon)

        if not a.no_figures:
            make_figures(mc, a.horizon, data_bits)
            fh.write("\n## Figures\n\n")
            for f in sorted(os.listdir(FIGDIR)):
                if f.startswith("fig_rf"):
                    fh.write(f"![{f}](figures/{f})\n\n")

    print(f"\n  results written to {RESULTS}")


if __name__ == "__main__":
    main()
