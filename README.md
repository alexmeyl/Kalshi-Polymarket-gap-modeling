# Modelling the NYC rent freeze

Vacancy and displacement effects of RGB Apartment & Loft Order #58, relative to a
counterfactual in which the Rent Guidelines Board had set a positive guideline.

```
rent_freeze_data.py    every published figure used, with its source
rent_freeze.py         the model: calibration, dynamics, Monte Carlo
run_rent_freeze.py     scenarios, tables, figures
RENT_FREEZE_RESULTS.md generated output
figures/fig_rf*.png    generated figures
```

Run it:

```bash
python run_rent_freeze.py --draws 500
```

---

## 0. One terminology correction, because it changes the object of study

The policy is a freeze on **rent stabilized** apartments: about 960,000 units
whose renewal increases are set each June by the NYC Rent Guidelines Board. It is
not a freeze on **rent controlled** apartments, a separate and nearly extinct
legacy programme of roughly 24,020 units whose rents move under the state's
Maximum Base Rent formula and are not touched by an RGB order. Everything below
concerns the stabilized stock. Where a source reports something only for "rent
regulated" housing, that is noted.

## 1. What actually happened

On 25 June 2026 the Rent Guidelines Board voted 7–1 to adopt Apartment & Loft
Order #58: **0.0% for one-year renewals and 0.0% for two-year renewals**, for
leases commencing 1 October 2026 through 30 September 2027. It is the first order
in the Board's history to set zero on a two-year lease. Because 57.6% of renewals
are taken as two-year leases, a single 0% order already locks the majority of
renewing tenants at zero through September 2029.

Under the Housing Stability and Tenant Protection Act of 2019 there is no separate
vacancy allowance, and Order #58 note 2 applies the renewal guideline to vacant
apartments that become occupied during the term. A 0% order is therefore 0% on
turnover as well — which matters a great deal for the supply side of the model.

## 2. The data

All figures are recorded with sources in `rent_freeze_data.py`. The ones that
drive the results:

### Cost of upkeep, last ten years

The Board's own Price Index of Operating Costs — a fixed-weight market basket of
taxes, labour, fuel, utilities, maintenance, administration and insurance, priced
each March for buildings containing rent stabilized apartments:

| Year | PIOC | Year | PIOC |
|---|---|---|---|
| 2017 | +6.2% | 2022 | +4.2% |
| 2018 | +4.5% | 2023 | +8.1% |
| 2019 | +5.5% | 2024 | +3.9% |
| 2020 | +3.7% | 2025 | +6.3% |
| 2021 | +3.0% | 2026 | +5.3% |

Mean 5.07%/yr; **cumulative +63.8% over 2017–2026**. The RGB projects +4.1% for
2027. Insurance rose a cumulative 99.9% over the last five years alone and fuel
63.0%, against 14.1% for taxes.

Against that, the guideline-driven rent roll — weighting one- and two-year orders
by the 42.4/57.6 lease mix — rose a cumulative **+17.4%** over the same ten years.
The freeze is being applied to a margin that has already been compressed for a
decade, which is why the counterfactual matters more than the freeze itself.

### Cost of upkeep in dollars, occupied and vacant

From Real Property Income and Expense filings with the Department of Finance,
reporting year 2024, per dwelling unit per month, for buildings containing at
least one stabilized unit:

| | $/unit/month |
|---|---|
| Average collected residential rent | 1,681 |
| Average total income (incl. commercial) | 1,890 |
| Average operating & maintenance cost | 1,203 (median 1,094) |
| Average net operating income | 688 |
| Residential-only buildings, O&M | 1,104 |
| Core Manhattan O&M | 2,042 |
| Bronx O&M | 977 |

Cost composition: taxes 26.3%, maintenance 17.4%, administration 12.7%, labour
11.2%, utilities 10.2%, insurance 8.9%, fuel 7.4%, miscellaneous 6.0%. 9.2% of
buildings spent more than they collected in 2024, against 4.9% in 2016.

**A note on the vacant-unit figure the question asked for.** The RGB does not
publish operating cost separately for occupied and vacant units, and RPIE filings
do not break expenses out that way — expenses are reported building-wide and are
not even separable between residential and commercial space. So the occupied /
vacant cost split is *constructed*, not observed: the model treats taxes and
insurance (35.2% of the budget) as continuing in full while a unit sits empty and
the remainder as scaling with occupancy, giving a carrying cost of roughly 45% of
the occupied figure. That 45% is a parameter, swept in the Monte Carlo, not a
measurement. Anyone who tells you the vacant-unit carrying cost is a known number
is quoting an assumption.

### Vacancy

Two different official measures, both correct, measuring different things:

- **Vacant and available** (2023 Housing and Vacancy Survey, Census/HPD): 1.41%
  citywide net rental vacancy, **0.98% among rent stabilized units**, 33,210 units
  available citywide. This is the statutory measure; it must stay under 5% for
  rent regulation to continue.
- **Registered as vacant** (HCR annual registrations, 1 April snapshots, obtained
  under FOIL): **3.7% in 2016 → ~7% in 2021 → 4.9% (≈49,000 units) in 2024 → 5.6%
  (≈57,000 units) in 2025.**

A warehoused unit is vacant but not available, so it appears in the second measure
and not the first. The rise in the second is the phenomenon of interest, and it is
the series the model is calibrated to.

### Tenants: income, rent, burden

From the 2023 HVS (household income for 2022), stabilized tenants, excluding those
receiving rental assistance:

| | |
|---|---|
| Median household income | $60,000 (vs $70,000 all renters, $90,800 market-rate) |
| Median contract rent | $1,500 (vs $2,000 market-rate) |
| Median contract rent / income | 27.0% |
| Rent burdened (>30%) | 45.5% |
| — moderately (30–50%) | 18.3% |
| — **severely (>50%)** | **27.2%** |

### Income growth, last ten years

This is where the sources disagree, and the disagreement is itself a modelling
input. The citywide *median renter income* rose 5.7% nominal / 1.8% real in 2024,
and average QCEW wages rose 6.1% nominal / 2.3% real through Q3 2025. But those
track a moving population. Held at a fixed point in the distribution, 2006–2023:

| Quintile | Nominal | Real | Implied nominal CAGR |
|---|---|---|---|
| Lowest | +34.9% | **−7.6%** | **1.78%/yr** |
| Highest | +81.9% | +24.7% | 3.58%/yr |

Rent-stabilized tenants sit near the bottom of that distribution. Their incomes
have been growing at under 2% nominal — below every guideline the Board has set
since 2022 and far below the 5.07%/yr at which the cost of running their buildings
has grown. The model gives each household an income growth rate interpolated along
this gradient by its position in the income distribution, which is what produces
the differential displacement risk.

## 3. Model

Full specification is in the `rent_freeze.py` module docstring. In outline: a
synthetic population of 80,000 units, each with a rent, an operating cost, a
sitting household's income, and a running balance of deferred maintenance,
simulated annually over six guideline years.

**Rent** grows by the lease-mix-weighted guideline `0.424·g₁ + 0.288·g₂`, plus
recapture of preferential rents to the legal rent at turnover — a channel that
survives a freeze, so a "freeze" still lets the rent roll grow about 0.5%/yr.

**Cost** grows by the PIOC (AR(1) around 5.07%, started at the RGB's own 4.1%
projection for 2027). As the operating margin falls, owners cut the discretionary
part of the budget (maintenance + administration, 30.1% of cost), and every dollar
skipped is booked to deferred maintenance.

**Warehousing.** A vacated unit returns to the market only if the owner can fund
the work. The binding constraint is cash, not net present value: the present value
of a stabilized tenancy comfortably exceeds any plausible renovation invoice, yet
57,000 units sat empty in April 2025. So the model compares the unit's own funding
capacity, `12 · max(NOI, 0) · φ`, against the job cost `K + deferred`, where φ is
how much of a dollar spent comes back as capitalised rent. **HSTPA is visible right
there**: improvement recovery ran at 1/40th of cost per month before 2019, worth
about **$2.66** of capitalised rent per dollar spent; today it is 1/144th capped at
$50,000 of spend, worth about **$0.74**. Renovation used to pay for itself and now
does not.

**Habitability failure** displaces sitting households at a hazard rising in
deferred maintenance relative to rent. This is the only supply-side channel in the
model that prices anyone out.

**Priced out** is defined as crossing 50% of income in contract rent — the standard
severe-burden line, and one the HVS measures directly for this population, so the
initial condition is observed rather than posited.

### Calibration and what identifies it

| Target | Source | Result |
|---|---|---|
| Rent-burden cross-section: median 27.0%, P(>30%)=45.5%, P(>50%)=27.2% | HVS 2023 via IA-2024 | lognormal, 2 parameters, 3 targets, worst residual 0.0018 |
| Cost-to-income: aggregate ratio 0.636 **and** 9.2% of buildings distressed | IE-2026 | requires the ratio to fall with income; supplied by the segment structure |
| Registered stabilized vacancy 5.6%, April 2025 | HCR registrations | fixes the warehousing logit intercept |
| Warehousing semi-elasticity | 2019 HSTPA episode | 0.028–0.056; swept over 0.02–0.08 |
| Severe-burden share stationary under a neutral rent path | internal consistency | fixes the entrant burden shift (≈ +0.5 in logs) |

Two of those deserve a note because they are easy to get wrong and both would have
produced a spurious result.

**Entrant rent burden.** Heavily burdened households move out at a higher hazard,
so if incoming tenants are drawn from the observed burden cross-section the upper
tail is steadily depleted and severe rent burden falls by about a fifth over six
years *in every scenario, freeze or not*. That is an artefact of churn, not a
finding. The model instead solves for the entrant burden shift that holds the
severe-burden share flat when rents and incomes grow at the same rate, which is
the correct null. The solved shift implies incoming tenants are roughly 1.6× as
rent burdened as the median sitting tenant — steep, but it is derived rather than
assumed, and it is the direction the HVS shows: stabilized tenants in post-1973
buildings, who have shorter tenancies, are 34.2% severely burdened against 25.6%
in pre-1974 buildings.

**Required versus actual maintenance spend.** The 2024 RPIE cost figure is what
owners actually spent, which already embodies whatever they were skipping. The
model therefore inverts the cut rule at t=0 to recover the underlying requirement,
so a building whose margin does not change keeps spending the observed amount and
the distressed-building share continues from the published 9.2% rather than
jumping.

Nothing here is estimated from a rent freeze, because no comparable freeze has
been run. The elasticity that drives the vacancy answer is anchored on HSTPA,
which cut exactly the quantity a freeze cuts — the cash available to turn a unit
over — and was followed by registered vacancy rising from 3.7% to 5.6%.
Attributing *all* of that rise to HSTPA gives a semi-elasticity of 0.056;
attributing half gives 0.028. That period also contains a pandemic and a Housing
Court backlog, so the upper end is an upper bound.

### Why there are three counterfactuals and not one

Regressing the one-year guideline on the contemporaneous PIOC gives a slope of
+0.33 (R²=0.21, p=0.21) over 2017–2025. Drop the two years that were themselves
freezes and **the slope collapses to +0.04 with R²=0.004 and p=0.89**: the Board's
guideline is statistically unrelated to the cost index it is required by statute
to consider. Fitting a single reaction function would be false precision, so the
model carries three:

| | one-year / two-year | basis |
|---|---|---|
| `low` | 2.32% / 3.97% | mean guideline 2017–2025 excluding freeze years |
| `central` | 3.00% / 5.20% | mean guideline 2022–2025, the most recent regime |
| `commensurate` | 0.649 × PIOC | the Board's own formula for holding NOI constant |

## 4. What the model does not do

It does not clear a market. Rents outside the stabilized stock are exogenous, so
the model says nothing about what a freeze does to market-rate rents, to the queue
of households who want a stabilized unit and cannot get one, or to household
formation. Warehoused units are reported as apartments withdrawn from
availability, **not** as households displaced — nobody is evicted by an empty
apartment. Displacement counts sitting households only.

Net additions to the stabilized stock (+21,281 in 2025, almost all new
construction taking a tax benefit) are exogenous to the RGB order and identical
across scenarios, so they are excluded; they cancel in every difference reported.

The freeze's effect on new supply — developers declining 485-x, owners pulling
units to condo conversion — is outside the model entirely and would push in the
direction of more scarcity than reported here.

## 5. Results

400 Monte Carlo draws, 80,000 synthetic units, six guideline years from 2026–27.
All figures are paired differences against the `central` counterfactual (3.0% /
5.2%), median with 5th–95th percentile in brackets, cumulative through 2031–32.
Full output in `RENT_FREEZE_RESULTS.md`.

### Base case: a three-year freeze

| | Difference vs no freeze |
|---|---|
| **Additional vacant stabilized apartments** | **+7,985  [2,346, 14,964]** |
| — registered vacancy rate | +0.85 pp [0.25, 1.59] (5.6% → ~6.5%) |
| **Fewer households paying >50% of income in rent** | **17,040  [13,915, 19,886]** |
| Fewer households paying >30% | 22,758 [18,815, 26,474] |
| Affordability-driven moves avoided | 9,535 [5,226, 15,156] |
| Additional displacements from habitability failure | 288 [−25, 817] |
| **Net households kept in their homes** | **9,247  [4,410, 15,181]** |
| Apartments permanently lost from the stock | +840 [179, 1,776] |
| Net operating income | −$177/unit/month |
| Buildings spending more than they collect | +5.07 pp (9% → ~15%) |
| Deferred maintenance | +$789/unit |

The two sides of the question do not come out symmetric. On the tenant side the
freeze is unambiguously protective and the effect is large: roughly 17,000 fewer
households in severe rent burden, and about 9,000 who do not have to move. On the
vacancy side it costs about 8,000 apartments, almost all of them warehoused rather
than destroyed — units that go empty and stay empty because the owner cannot fund
the turnover, not units that are demolished. Permanent losses are two orders of
magnitude smaller than the burden relief.

**Roughly two households are spared severe rent burden for each apartment that
goes vacant.** That ratio improves with duration (3.2 : 1 over a six-year freeze)
because burden relief compounds while the warehousing response is partly bounded
by the turnover rate — warehousing can only happen when a unit turns over, and the
freeze itself reduces turnover.

### It depends more on the counterfactual than on the freeze

| Counterfactual | Extra vacant apartments | Fewer severely burdened |
|---|---|---|
| `low` (2.3%) | 5,336 [1,579, 10,380] | 8,010 [5,567, 10,572] |
| `central` (3.0%) | 7,985 [2,346, 14,964] | 17,040 [13,915, 19,886] |
| `commensurate` (0.649 × PIOC) | 8,680 [2,663, 15,746] | 26,052 [22,966, 28,706] |

The affordability benefit more than triples across this range while the vacancy
cost only rises about 60%. Since the Board's guideline has historically been
uncorrelated with its own cost index, this spread is not resolvable from the data
— it is a statement about what the Board would have done, not about how the world
works.

### Freeze duration

| Length | Extra vacant | Fewer severely burdened | Apartments lost |
|---|---|---|---|
| 1 year (Order #58 as adopted) | 3,006 [509, 6,217] | 5,346 [3,120, 7,285] | 342 |
| 2 years | 5,550 [1,596, 10,690] | 10,980 [8,195, 13,285] | 636 |
| 3 years | 7,985 [2,346, 14,964] | 17,040 [13,915, 19,886] | 840 |
| 4 years | 9,925 [2,974, 18,287] | 23,472 [19,881, 26,438] | 1,038 |
| 6 years | 11,863 [3,603, 21,392] | 38,064 [34,640, 41,065] | 1,158 |

Both effects grow with duration, but the vacancy cost decelerates and the
affordability benefit does not. What does deteriorate sharply with duration is
owner finance: under a six-year freeze the share of buildings spending more than
they collect roughly triples, from about 9% today to around 24%, and mean net
operating income falls from $770 to $460 per unit per month. Most of that damage
has not yet shown up as vacancy inside the six-year window. A model that stopped
at vacancy counts would understate what a long freeze does.

### What the answer rests on

| Parameter | Correlation with extra vacancy |
|---|---|
| `warehouse_slope` (HSTPA-anchored semi-elasticity) | **+0.80** |
| `turnover` | +0.43 |
| `max_cut` (how far owners cut maintenance) | −0.16 |
| everything else | < 0.15 |

One parameter dominates, and it is the one that is not directly observed. The
5th–95th range on extra vacant apartments, 2,300 to 15,000, is mostly this single
uncertainty. Narrowing it requires knowing how much of the 3.7% → 5.6% rise in
registered vacancy after 2019 was HSTPA and how much was the pandemic and the
Housing Court backlog — a question the FOIL'd registration data could probably
answer with unit-level durations, and which no published source currently does.

### Caveats that cut against the freeze

Three effects are outside the model and all point the same way — more scarcity
than reported:

1. **No market clearing.** Households who cannot find a stabilized unit are not in
   the population. An extra 8,000 warehoused apartments in a city with a 1.41% net
   rental vacancy rate has consequences for people the model never sees.
2. **New supply.** Developer response to the regulatory climate is exogenous here.
3. **The stock is not uniform.** About 460,000 units sit in buildings that are 90%+
   stabilized and have no market-rate cross-subsidy. The model's segment structure
   captures some of this, but the tail risk of concentrated building failure in
   that segment is handled by a smooth hazard, which will understate cluster
   effects if a cohort of buildings fails together.

## Sources

Also machine-readable in `rent_freeze_data.SOURCES`.

### Cost of upkeep — the price index, ten years

The headline PIOC change for each year was read out of that year's report:

| Year | Value | URL |
|---|---|---|
| 2026 | +5.3% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2026/04/2026-PIOC.pdf> |
| 2025 | +6.3% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2025/04/2025-PIOC.pdf> |
| 2024 | +3.9% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2024/04/2024-PIOC.pdf> |
| 2023 | +8.1% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2023/04/2023-PIOC.pdf> |
| 2022 | +4.2% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2022/04/2022-PIOC.pdf> |
| 2021 | +3.0% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2021/04/2021-PIOC.pdf> |
| 2020 | +3.7% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2020/04/2020-PIOC.pdf> |
| 2019 | +5.5% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2019/08/2019-PIOC.pdf> |
| 2018 | +4.5% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2019/08/2018-PIOC.pdf> |
| 2017 | +6.2% | <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2019/08/2017-PIOC.pdf> |

**Extraction note.** The 2017 and 2018 reports embed subset fonts with no
ToUnicode map; `pypdf` returns scrambled text for them and silently yields nothing
useful. PyMuPDF decodes them correctly. Anyone rebuilding this series should use
PyMuPDF and check that the extracted header names the expected year.

### Cost of upkeep in dollars — RPIE filings

- 2026 Income and Expense Study (O&M per unit, NOI, cost composition, distressed
  buildings; reporting year 2024):
  <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2026/03/2026-IE-Study-Final.pdf>
- 2025 Income and Expense Study (reporting year 2023, and the 64.9%
  cost-to-income pass-through used in the commensurate formula):
  <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2025/03/2025-IE-Study.pdf>

### Tenant income, rent and burden

- 2026 Income and Affordability Study (renter income growth, CPI, wages, poverty;
  and the RGB's presentation of the 2023 HVS income and rent figures):
  <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2026/04/2026-IA.pdf>
- 2024 Income and Affordability Study — **the split of rent burden into moderate
  (18.3%) and severe (27.2%), and the 27.0% median contract-rent-to-income ratio
  for stabilized tenants without rental assistance**, which are the three targets
  the burden distribution is fitted to and do not appear in later editions:
  <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2024/04/2024-IA-Study.pdf>
- 2025 Income and Affordability Study (household income by quintile, 2006–2023):
  <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2025/04/2025-IA-Study.pdf>

**HVS note.** The 2023 Housing and Vacancy Survey figures are taken as the RGB
reports them, not from the Census/HPD microdata release. The RGB's presentation
excludes households receiving rental assistance or living in public housing, which
is what makes the burden figures usable as a model target — the raw HVS tables do
not apply that exclusion and record Section 8 households at rent-to-income ratios
far above what they actually pay.

### Stock, supply, guidelines, vacancy

- Apartment Orders #1 through #58 (guideline history):
  <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2025/07/RGB-Apartment-Chart.pdf>
- 2026-27 Apartment/Loft Order #58:
  <https://rentguidelinesboard.cityofnewyork.us/2026-27-apartment-loft-order-58/>
- 2026 Housing Supply Report:
  <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2026/05/2026-HSR.pdf>
- 2026 Changes to the Rent Stabilized Housing Stock:
  <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2026/05/2026-Changes.pdf>
- Housing NYC: Rents, Markets and Trends 2025:
  <https://rentguidelinesboard.cityofnewyork.us/wp-content/uploads/2025/11/HNYC-2025.pdf>
- RGB research index: <https://rentguidelinesboard.cityofnewyork.us/research/>
- Registered stabilized vacancy (HCR 1 April registration snapshots obtained under
  FOIL; the 3.7% → 5.6% series and the 49,000 → 57,000 unit counts):
  <https://www.thecityreporter.nyc/2026/07/06/vacant-affordable-apartments-housing-rate/>
  — a news report of FOIL'd data, not a published dataset, and the weakest link in
  the calibration chain. The model's warehousing level is fitted to it.
