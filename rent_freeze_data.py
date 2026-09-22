"""Empirical inputs for the NYC rent-freeze model.

Every number in this module is a published figure, with its source recorded next to
it. Nothing here is fitted or assumed; fitted quantities live in `rent_freeze.py`
(calibration) and assumed quantities are collected in `rent_freeze.Params` so that
the boundary between "measured" and "assumed" stays visible.

SOURCE KEYS
-----------
PIOC-yyyy   NYC Rent Guidelines Board, "yyyy Price Index of Operating Costs"
IE-yyyy     NYC RGB, "yyyy Income and Expense Study" (analyses DOF RPIE filings,
            reporting year = yyyy - 2)
IA-yyyy     NYC RGB, "yyyy Income and Affordability Study"
HSR-yyyy    NYC RGB, "yyyy Housing Supply Report"
CHG-yyyy    NYC RGB, "yyyy Changes to the Rent Stabilized Housing Stock"
HVS-2023    US Census Bureau / NYC HPD, 2023 NYC Housing and Vacancy Survey
APT-CHART   NYC RGB, "Apartment Orders #1 through #58" summary chart
HCR-FOIL    NYS Homes & Community Renewal annual registration snapshots (April 1),
            obtained under FOIL and reported by THE CITY, 6 July 2026

A NOTE ON TERMINOLOGY. The policy is a freeze on RENT STABILIZED units -- roughly
960,000-1,000,000 apartments whose renewal increases are set annually by the Rent
Guidelines Board. It is not a freeze on RENT CONTROLLED units, a separate legacy
programme of about 24,020 apartments (CHG-2026) whose rents move under the Maximum
Base Rent formula administered by the state, not the RGB. This module describes the
stabilized stock.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 0. Source documents
# ---------------------------------------------------------------------------
# Every figure below was read out of one of these. The PIOC series was extracted
# with PyMuPDF: the 2017 and 2018 reports embed subset fonts with no ToUnicode
# map, so pypdf returns scrambled text for them and must not be used.

_RGB = "https://rentguidelinesboard.cityofnewyork.us"
_UP = _RGB + "/wp-content/uploads"

SOURCES = {
    # --- index
    "RGB research reports (index)": _RGB + "/research/",

    # --- cost of upkeep: the price index, ten years
    "PIOC-2026": _UP + "/2026/04/2026-PIOC.pdf",
    "PIOC-2025": _UP + "/2025/04/2025-PIOC.pdf",
    "PIOC-2024": _UP + "/2024/04/2024-PIOC.pdf",
    "PIOC-2023": _UP + "/2023/04/2023-PIOC.pdf",
    "PIOC-2022": _UP + "/2022/04/2022-PIOC.pdf",
    "PIOC-2021": _UP + "/2021/04/2021-PIOC.pdf",
    "PIOC-2020": _UP + "/2020/04/2020-PIOC.pdf",
    "PIOC-2019": _UP + "/2019/08/2019-PIOC.pdf",
    "PIOC-2018": _UP + "/2019/08/2018-PIOC.pdf",
    "PIOC-2017": _UP + "/2019/08/2017-PIOC.pdf",

    # --- cost of upkeep in dollars: RPIE filings
    "IE-2026": _UP + "/2026/03/2026-IE-Study-Final.pdf",
    "IE-2025": _UP + "/2025/03/2025-IE-Study.pdf",

    # --- tenant income, rent burden, affordability
    "IA-2026": _UP + "/2026/04/2026-IA.pdf",
    "IA-2025": _UP + "/2025/04/2025-IA-Study.pdf",
    "IA-2024": _UP + "/2024/04/2024-IA-Study.pdf",   # moderate/severe burden split

    # --- stock, supply, guidelines
    "HSR-2026":  _UP + "/2026/05/2026-HSR.pdf",
    "CHG-2026":  _UP + "/2026/05/2026-Changes.pdf",
    "HNYC-2025": _UP + "/2025/11/HNYC-2025.pdf",
    "APT-CHART": _UP + "/2025/07/RGB-Apartment-Chart.pdf",
    "Order #58": _RGB + "/2026-27-apartment-loft-order-58/",

    # --- registered (as opposed to available) vacancy
    "HCR-FOIL": "https://www.thecityreporter.nyc/2026/07/06/"
                "vacant-affordable-apartments-housing-rate/",
}

# NOTE ON THE HVS. The 2023 Housing and Vacancy Survey figures used here (tenant
# incomes, contract rents, rent burden, vacancy rates) are taken as the RGB
# reports them in IA-2024 and IA-2026, not from the Census/HPD microdata release.
# The RGB's presentation excludes households receiving rental assistance, which
# is what makes the burden figures usable as a model target; the raw HVS tables
# do not apply that exclusion.


# ---------------------------------------------------------------------------
# 1. The policy itself
# ---------------------------------------------------------------------------

# RGB Apartment & Loft Order #58, adopted 25 June 2026 by a 7-1 vote, covering
# leases commencing 1 Oct 2026 - 30 Sep 2027.  [APT-CHART; Order #58]
ORDER_58 = {"year": 2026, "one_year_pct": 0.0, "two_year_pct": 0.0}

# Order #58 note 2: under HSTPA there is no separate vacancy allowance; the renewal
# guideline also applies to vacant apartments that become occupied during the term.
# So a 0% order is 0% on turnover too.  [APT-CHART note 1-2]
VACANCY_ALLOWANCE_PCT = 0.0

# Guideline history. Values are the headline renewal adjustments; `two_year_total`
# is the cumulative increase over the full two-year term (some orders split it).
# Key: calendar year in which the order takes effect (1 Oct).  [APT-CHART]
GUIDELINES = {
    #  year: (order #, one-year %, two-year total % over the 2-year term)
    2015: (47, 0.00, 2.00),
    2016: (48, 0.00, 2.00),
    2017: (49, 1.25, 2.00),
    2018: (50, 1.50, 2.50),
    2019: (51, 1.50, 2.50),
    2020: (52, 0.00, 1.00),   # 0% yr 1, +1.0% yr 2
    2021: (53, 0.75, 2.50),   # 0% first 6 months, 1.5% last 6 months -> 0.75% avg
    2022: (54, 3.25, 5.00),
    2023: (55, 3.00, 6.04),   # 2.75% yr 1 then 3.2% yr 2, compounded
    2024: (56, 2.75, 5.25),
    2025: (57, 3.00, 4.50),
    2026: (58, 0.00, 0.00),   # THE FREEZE
}

# Share of renewals taken as one- vs two-year leases, from 2024 HCR registration
# files. Used by the RGB itself in its commensurate formulas.  [PIOC-2025 endnote 8]
LEASE_MIX_ONE_YEAR = 0.424
LEASE_MIX_TWO_YEAR = 0.576


# ---------------------------------------------------------------------------
# 2. Cost of upkeep: the Price Index of Operating Costs
# ---------------------------------------------------------------------------

# Annual % change in the PIOC for buildings containing rent stabilized apartments.
# The PIOC is a fixed-weight market basket priced each March; it is the RGB's own
# measure of "cost of upkeep" and is the statutory input to the guideline decision.
# [PIOC-2017 .. PIOC-2026]
PIOC_PCT_CHANGE = {
    2017: 6.2,
    2018: 4.5,
    2019: 5.5,
    2020: 3.7,
    2021: 3.0,
    2022: 4.2,
    2023: 8.1,
    2024: 3.9,
    2025: 6.3,
    2026: 5.3,
}

# The RGB's own projection for the next index year.  [PIOC-2026 p.10]
PIOC_PROJECTION_2027 = 4.1

# "Core" PIOC excludes heating fuel; it is the cleaner inflation signal. [PIOC-2026]
CORE_PIOC_PCT_CHANGE = {2019: 4.9, 2020: 5.1, 2021: 3.5, 2022: 3.0,
                        2023: 7.2, 2024: 4.9, 2025: 6.0, 2026: 4.8}

# 2026 PIOC expenditure weights (% of the basket) and this year's price change.
# [PIOC-2026 p.5]
PIOC_2026_WEIGHTS = {
    "taxes":          27.9,
    "maintenance":    18.5,
    "administrative": 13.5,
    "labor":          11.9,
    "utilities":      10.9,
    "insurance":       9.5,
    "fuel":            7.9,
}
PIOC_2026_COMPONENT_CHANGE = {
    "taxes":           2.6,
    "maintenance":     6.0,
    "administrative":  4.8,
    "labor":           3.0,
    "utilities":       5.6,
    "insurance":      10.5,
    "fuel":           11.0,
}

# Five-year cumulative change, 2021->2026.  [PIOC-2026 p.6]
PIOC_5YR_CUMULATIVE = 31.0
PIOC_5YR_CUMULATIVE_BY_COMPONENT = {
    "insurance": 99.9, "fuel": 63.0, "maintenance": 36.7, "taxes": 14.1,
}


# ---------------------------------------------------------------------------
# 3. Cost of upkeep: actual dollars per unit (RPIE filings)
# ---------------------------------------------------------------------------
# The PIOC is an index; RPIE statements filed with the NYC Department of Finance
# give the levels. All figures are per dwelling unit per MONTH for buildings
# containing at least one rent stabilized unit, reporting year 2024. [IE-2026]

RPIE_YEAR = 2024

RPIE_2024 = {
    "collected_rent":        1681.0,  # avg monthly collected residential rent
    "total_income":          1890.0,  # incl. commercial space and other income
    "om_cost_unadjusted":    1203.0,  # avg monthly operating & maintenance cost
    "om_cost_adjusted":      1166.0,  # after RGB's -3.07% reporting adjustment
    "om_cost_median":        1094.0,
    "noi":                    688.0,  # total_income - om_cost_unadjusted
    "om_residential_only":   1104.0,  # buildings with no commercial space
    "om_residential_adj":    1070.0,
}

# Year-over-year changes, 2023 -> 2024.  [IE-2026 highlights]
RPIE_2024_GROWTH = {
    "rental_income":  4.8,
    "total_income":   4.9,
    "operating_cost": 4.2,
    "noi_nominal":    6.2,
    "noi_real":       2.2,
}

# Average monthly O&M cost per unit by borough, 2024.  [IE-2026 p.8]
OM_COST_BY_BOROUGH = {
    "Manhattan":      1659.0,
    "Core Manhattan": 2042.0,   # south of W 110th / E 96th
    "Upper Manhattan":1248.0,
    "Queens":         1125.0,
    "Brooklyn":       1068.0,
    "Bronx":           977.0,
    "Staten Island":   895.0,
    "City excl. Core Manhattan": 1073.0,
}

# Composition of operating cost, share of total, 2024 RPIE.  [IE-2026 p.8]
OM_COST_SHARES = {
    "taxes": 26.3, "maintenance": 17.4, "administrative": 12.7, "labor": 11.2,
    "utilities": 10.2, "insurance": 8.9, "fuel": 7.4, "miscellaneous": 6.0,
}

# Components a landlord can plausibly cut in the short run without violating the
# warranty of habitability: discretionary maintenance and administration. Taxes,
# insurance, fuel, utilities and (largely unionised) labour are not discretionary.
DISCRETIONARY_COST_SHARE = (OM_COST_SHARES["maintenance"]
                            + OM_COST_SHARES["administrative"]) / 100.0  # 0.301

# Ratio of average operating cost to average income -- the RGB uses this as the
# pass-through weight in its "Net Revenue" commensurate formula. [PIOC-2025 endnote 8]
COST_TO_INCOME_RATIO = 0.649
COST_TO_INCOME_CORE_MANHATTAN = 0.564   # [IE-2026 p.11]
COST_TO_INCOME_REST_OF_CITY = 0.638     # [IE-2026 p.11]

# Share of buildings whose O&M cost exceeds gross income ("distressed"). [IE-2026 p.9]
DISTRESSED_SHARE = {1990: 13.9, 2016: 4.9, 2022: 9.8, 2023: 9.3, 2024: 9.2}


# ---------------------------------------------------------------------------
# 4. Vacancy
# ---------------------------------------------------------------------------

# (a) Census/HPD survey measure: units vacant AND AVAILABLE for rent. This is the
#     legal trigger for continuing rent regulation (must stay below 5%). [HVS-2023]
HVS_2023_VACANCY = {
    "citywide_net_rental":   1.41,
    "rent_stabilized":       0.98,
    "Manhattan":             2.33,
    "Bronx":                 0.88,
    "vacant_available_units": 33210,
}

# (b) HCR registration measure: units a landlord registered as VACANT on April 1,
#     whether or not they are on the market. This is the measure that captures
#     warehousing, and it is the one that has moved. [HCR-FOIL via THE CITY, 2026]
STABILIZED_VACANCY_REGISTERED = {
    2016: 3.7,
    2021: 7.0,   # pandemic peak, approximate
    2024: 4.9,   # ~49,000 units
    2025: 5.6,   # 57,000 units of ~1.02m registered
}
REGISTERED_VACANT_UNITS = {2024: 49000, 2025: 57000}

# The two measures are not contradictory: a warehoused unit is vacant but not
# available, so it enters (b) and not (a).


# ---------------------------------------------------------------------------
# 5. The stock
# ---------------------------------------------------------------------------

STABILIZED_UNITS = 960_000        # working figure; press usage is "about 1 million"
STABILIZED_UNITS_RANGE = (940_000, 1_020_000)
RENT_CONTROLLED_UNITS = 24_020    # [CHG-2026] -- NOT covered by the RGB freeze

# Units in buildings that are 90%+ rent stabilized: the stock with no market-rate
# cross-subsidy, and the segment where a freeze binds hardest.
HEAVILY_STABILIZED_UNITS = 460_000

# Flows into and out of stabilization, 2025.  [CHG-2026]
STOCK_FLOWS_2025 = {"entered": 32_745, "left": 11_464}
STOCK_FLOWS_1994_2025 = {"entered": 243_443, "left": 360_914, "net": -117_471}

# Gap between the legal rent registered with HCR and the rent actually collected
# (RPIE), 2023 -- largely preferential rents. On vacancy the owner may reset to the
# legal rent, so this gap is a revenue channel independent of the RGB order.
LEGAL_VS_COLLECTED_GAP = {
    "citywide": 23.6, "Staten Island": 41.4, "Bronx": 26.1,
    "Queens": 24.9, "Brooklyn": 20.9, "Manhattan": 20.6,
}

# Individual Apartment Improvement recovery under HSTPA: at most $50,000 of spend
# over 15 years, yielding at most about $347/month of permanent rent. [HSTPA 2019]
IAI_SPEND_CAP = 50_000.0
IAI_MAX_MONTHLY_RECOVERY = 347.0


# ---------------------------------------------------------------------------
# 6. Tenants: income, rent, burden
# ---------------------------------------------------------------------------

# 2023 HVS, reporting household income for calendar 2022.  [HVS-2023 via IA-2026]
HVS_2023_TENANTS = {
    "median_income_all_renters":        70_000.0,
    "median_income_stabilized":         60_000.0,
    "median_income_stabilized_pre74":   60_000.0,
    "median_income_stabilized_post73":  50_000.0,
    "median_income_market":             90_800.0,
    "median_contract_rent_all":          1_641.0,
    "median_contract_rent_stabilized":   1_500.0,
    "median_contract_rent_pre74":        1_471.0,
    "median_contract_rent_post73":       1_627.0,
    "median_contract_rent_market":       2_000.0,
    # Gross rent / income, excluding Section 8 households
    "gross_rent_to_income_all":            28.2,
    "gross_rent_to_income_stabilized":     28.8,
    "gross_rent_to_income_market":         27.3,
    # Share paying >30% of income in CONTRACT rent, excluding rental assistance
    "rent_burdened_all":                   43.1,
    "rent_burdened_stabilized":            45.5,
    "rent_burdened_stabilized_pre74":      43.8,
    "rent_burdened_stabilized_post73":     53.0,
    "rent_burdened_market":                40.6,
    # Split of that burden into moderate (30-50%) and severe (>50%).  [IA-2024 p.14]
    "moderately_burdened_stabilized":      18.3,
    "severely_burdened_stabilized":        27.2,
    "moderately_burdened_all":             18.1,
    "severely_burdened_all":               25.0,
    "severely_burdened_stabilized_pre74":  25.6,
    "severely_burdened_stabilized_post73": 34.2,
    "severely_burdened_market":            22.7,
    # Median CONTRACT rent / income for stabilized tenants without rental
    # assistance -- the central tendency the burden distribution must reproduce.
    "median_contract_rent_to_income_stabilized": 27.0,   # [IA-2024 p.14]
}

# The three burden facts a fitted distribution of rent burden must match:
# median 27.0%, P(burden > 30%) = 45.5%, P(burden > 50%) = 27.2%. Two free
# parameters, three targets, so the fit is falsifiable. See rent_freeze.fit_burden.
BURDEN_TARGETS = {"median": 0.270, "p_over_30": 0.455, "p_over_50": 0.272}

# 2024 ACS, whole renter population (not stabilized-specific).  [IA-2026]
ACS_2024_RENTERS = {
    "share_paying_30pct_or_more": 51.6,
    "share_paying_50pct_or_more": 28.8,
    "median_gross_rent_to_income": 30.9,
}

# Income growth. Two different things are measured here and they disagree, which is
# itself a modelling input: the citywide median moves with the composition of who
# rents, while the quintile series tracks growth at a fixed point in the
# distribution. Rent-stabilized tenants sit near the bottom two quintiles.
INCOME_GROWTH_2024 = {"median_renter_nominal": 5.7, "median_renter_real": 1.8}
WAGE_GROWTH_2025 = {"qcew_nominal": 6.1, "qcew_real": 2.3}   # Q4-24 through Q3-25

# Point-to-point household income change by quintile, 2006-2023 (17 years). [IA-2025]
INCOME_BY_QUINTILE_2006_2023 = {
    #  quintile: (nominal % change, real % change)
    "lowest":  (34.9, -7.6),
    "highest": (81.9, 24.7),
}
# Implied nominal CAGR: lowest 1.78%/yr, highest 3.58%/yr.
INCOME_CAGR_NOMINAL_LOWEST_QUINTILE = (1.349 ** (1 / 17) - 1) * 100   # 1.78
INCOME_CAGR_NOMINAL_HIGHEST_QUINTILE = (1.819 ** (1 / 17) - 1) * 100  # 3.58

# Inflation, NYC metropolitan area.  [IA-2026]
CPI_2025 = 3.4
CPI_2025_EX_SHELTER = 2.7
CPI_2025_RENT_INDEX = 4.7

# Poverty: share of renters below the Supplemental Poverty Measure threshold,
# 2022-2024 pooled, Columbia Poverty Tracker.  [IA-2026]
POVERTY_TRACKER = {
    "below_spm_stabilized": 27.0, "below_spm_market": 29.0,
    "below_200pct_spm_stabilized": 67.0, "below_200pct_spm_market": 62.0,
}


# ---------------------------------------------------------------------------
# 7. Convenience accessors
# ---------------------------------------------------------------------------

def pioc_series(start: int = 2017, end: int = 2026):
    """Return (years, percent changes) for the PIOC over a closed year range."""
    ys = [y for y in sorted(PIOC_PCT_CHANGE) if start <= y <= end]
    return ys, [PIOC_PCT_CHANGE[y] for y in ys]


def guideline_series(start: int = 2015, end: int = 2026):
    """Return (years, one-year %, two-year total %) over a closed year range."""
    ys = [y for y in sorted(GUIDELINES) if start <= y <= end]
    return (ys,
            [GUIDELINES[y][1] for y in ys],
            [GUIDELINES[y][2] for y in ys])


def mean_pioc(start: int = 2017, end: int = 2026) -> float:
    """Arithmetic mean annual PIOC change over a closed year range, in percent."""
    _, v = pioc_series(start, end)
    return sum(v) / len(v)


def effective_guideline(year: int) -> float:
    """Lease-mix-weighted average rent-roll growth implied by a guideline year.

    A one-year lease resets every year; a two-year lease resets every other year,
    so in steady state half of the two-year cohort takes its increase in any given
    year. The rent roll therefore grows by

        g_hat = s1 * g1 + (s2 / 2) * g2_total

    where g2_total is the cumulative increase over the two-year term.
    """
    _, g1, g2 = GUIDELINES[year]
    return LEASE_MIX_ONE_YEAR * g1 + (LEASE_MIX_TWO_YEAR / 2.0) * g2


if __name__ == "__main__":  # quick integrity check of the recorded figures
    ys, v = pioc_series()
    print(f"PIOC {ys[0]}-{ys[-1]}: mean {mean_pioc():.2f}%/yr, "
          f"cumulative {100 * (_c := __import__('math').prod(1 + x / 100 for x in v)) - 100:.1f}%")
    print(f"Guideline mean 1-yr 2017-2025: "
          f"{sum(GUIDELINES[y][1] for y in range(2017, 2026)) / 9:.2f}%")
    noi = RPIE_2024["total_income"] - RPIE_2024["om_cost_unadjusted"]
    print(f"NOI check: {noi:.0f} vs reported {RPIE_2024['noi']:.0f}")
    print(f"PIOC weights sum: {sum(PIOC_2026_WEIGHTS.values()):.1f}")
    print(f"Discretionary cost share: {DISCRETIONARY_COST_SHARE:.3f}")
