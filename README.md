# Kalshi vs. Polymarket: how fast do price gaps close?

AM215 mini-project · Alex Meylikhov · Ravi Tripathi · Ved Pant ·  Fall 2026

## The question

Kalshi and Polymarket often list the same real-world event, but the two prices for it don't always match. This project asks two things:

1. **How fast does a gap between the two prices close?**
2. **How big does the gap need to get before it starts closing?**

The second question matters because arbitrage isn't free. If fees and other trading costs eat a 1-cent gap, nobody has a reason to trade it away, so small gaps can persist. Big gaps should get pulled back.

## The model

Let G(t) = Kalshi price − Polymarket price. The model is

```
G(t+1) = G(t) − κ · max(0, |G(t)| − c) · sign(G(t)) + noise
```

- Below the threshold **c**, nothing pulls the gap back and it just wanders.
- Above **c**, it is pulled toward the threshold at rate **κ**.
- We read **c** as a stand-in for transaction costs.
- Setting **c = 0** gives ordinary mean reversion. That's our verification check: the fitted model should agree with the closed-form answer in that limit.
- One step is **5 minutes**, and G(t) is measured from each market's median gap (see [How the model is fitted](#how-the-model-is-fitted)). We report κ as a **half-life**: the minutes it takes for the part of a gap beyond c to halve.

## Where the project stands

**Done:**
- Data collection for nine events at 1-minute resolution, cleaned of settlement artifacts and aligned into a gap series for each.
- A first fit of the threshold model (c and κ for each event) with bootstrap error bars.
- Four validation checks: time-step consistency, simulation recovery of known values, the c = 0 check against the closed-form result, and an out-of-sample comparison against simpler models.

**Not done yet:** a model that handles the two problems the checks found (gaps close at two speeds, and the offset between platforms drifts), more events, and packaging. See [What's next](#whats-next).

The results are a work in progress: the method checks out, but only some markets show a clear band. See [First model results](#first-model-results).

## The nine events

Three per category. For each event we track one outcome and use the same outcome on both platforms.

| Category | Event | Outcome tracked |
|---|---|---|
| Politics | 2024 US presidential election | Trump wins |
| Politics | Sept 2026 FOMC decision | 25bp hike |
| Politics | Oct 2025 government shutdown | Shutdown occurs |
| Sports | Super Bowl LX | Seattle wins |
| Sports | 2025 World Series | Dodgers win |
| Sports | 2025 NBA Finals | Thunder win |
| Culture | 2025 papal conclave | Prevost elected |
| Culture | 2025 Oscars, Best Picture | Anora wins |
| Culture | Taylor Swift engagement | Yes |

## Repo layout

```
notebook/
  pull_all_events.ipynb    # downloads, cleans, aligns, and plots everything
  fit_kappa.ipynb          # fits c and κ, runs the validation checks, makes the figures
results/
  summary.csv              # one row per event
  <event>/gap.csv          # aligned prices and the gap, with outlier flags
  <event>/gap_plot.png     # prices on top, gap below
pilot_pull.py, FOMC.ipynb  # early one-event experiments, superseded by the notebook
```

The pull notebook writes to a folder called `out/`. The `results/` folder in this repo is a saved copy of one run of that notebook. The fitting notebook reads `results/` (or `out/`) and writes its tables and figures to `fit_out/`, which isn't committed.

## How to run it

1. Open `notebook/pull_all_events.ipynb` in Jupyter or Google Colab.
2. Run it top to bottom (about 2 minutes). It needs `requests`, `pandas`, and `matplotlib`. No API keys are needed, since both platforms' price endpoints are public.
3. Outputs appear in `out/`. Check the `status` column of `out/summary.csv`: it says `ok` unless a download failed.

The settings at the top of the notebook control the bar size (`BAR_MINUTES`, default 1; set 60 for hourly), the Kalshi spread filter, and the outlier flag. The `EVENTS` list holds each event's Kalshi ticker, Polymarket token ID, and date range. An event marked `FILL_IN` is skipped.

To fit the model:

1. Open `notebook/fit_kappa.ipynb` in Jupyter or Colab and run it top to bottom (about 5 minutes; the simulations take most of it). It needs `pandas`, `numpy`, and `matplotlib`.
2. It looks for `results/` next to it. In Colab, where the repo isn't available, it asks you to upload `results.zip`, a zip of the `results/` folder.
3. Every figure has a "How to read this" caption, and the notebook ends with a generated summary and a table of which results can be trusted.

## How the data is pulled

A few decisions worth knowing about, because most of them came from something breaking:

- **Kalshi has two tiers.** Recent markets are served by the live API, and older ones by a separate `/historical/` API with different URLs and field names. The notebook looks the ticker up to find its tier and close time, and reads prices in dollars from the field names rather than guessing units.
- **Both platforms cap request size.** Kalshi allows at most 5,000 candles per request, and Polymarket about two weeks. Long ranges are downloaded in chunks. Failed requests are retried, and any chunk that still fails is counted in the summary.
- **Polymarket uses the CLOB endpoint at 1-minute fidelity.** `clob.polymarket.com/prices-history` with `fidelity=1` returns 1-minute data for all nine markets. The `data-api.polymarket.com/v2/prices-history` endpoint returns nothing for these older markets, so it isn't used.
- **Each Polymarket token is checked.** The notebook confirms the token is the "Yes" side of the market before pulling it, and prints both platforms' market titles so you can see they ask the same question.
- **Both prices are quote midpoints.** Kalshi's price is the bid/ask midpoint at the end of each 1-minute bar. Polymarket's history appears to be midpoint-based too (its half-tick values such as 0.875 suggest this). Kalshi's last-trade price is saved as `kalshi_last` for comparison.
- **Data stops before settlement.** When a Kalshi market closes, its book goes to bid 0 / ask 1, whose midpoint is exactly 0.50. That produced the ~0.5 "gaps" in the first pull. Each series now stops at the earlier of the two markets' close times, and Kalshi bars with a spread wider than 10 cents are dropped. Prices outside [0, 1] are dropped and counted.
- **The two series are never resampled or forward-filled.** Doing that creates a fake lag between the platforms. Instead, each Kalshi bar is paired with the nearest Polymarket point within ±30 seconds, each point is used at most once, and bars with no match are dropped. The offset is saved as `poly_offset_s`.
- **Outliers are flagged, not deleted.** A point is flagged when it sits more than 5 MADs from the median gap within ±15 minutes. The MAD has a floor of half a cent, so a spike in a flat stretch still gets flagged. The flag means "looks structurally unusual," not "confirmed bad."

## What the data shows so far

From `results/summary.csv`, after the cleaning above. Outliers are flagged but still included.

| Event | Matched points | Mean gap | Mean abs gap | Max abs gap | Flagged |
|---|---|---|---|---|---|
| 2024 election | 25,219 | −0.032 | 0.032 | 0.069 | 0 |
| Sept 2026 FOMC | 17,460 | 0.006 | 0.011 | 0.120 | 1 |
| Oct 2025 shutdown | 17,036 | 0.005 | 0.020 | 0.140 | 8 |
| Super Bowl LX | 49,640 | 0.002 | 0.008 | 0.060 | 0 |
| 2025 World Series | 29,418 | 0.008 | 0.011 | 0.105 | 7 |
| 2025 NBA Finals | 37,537 | −0.003 | 0.007 | 0.110 | 6 |
| 2025 papal conclave | 2,679 | 0.000 | 0.004 | 0.020 | 0 |
| 2025 Oscars | 3,567 | −0.008 | 0.019 | 0.095 | 1 |
| Taylor Swift engagement | 16,990 | 0.003 | 0.031 | 0.220 | 38 |

Prices are implied probabilities from 0 to 1, so a gap of 0.01 is one cent. The ~0.5 gaps from the first pull are gone; the largest gaps left are 2–22 cents with tight Kalshi spreads, so they look like real disagreements.

## How the model is fitted

Every choice is also explained in the "Choices and why" table at the top of `fit_kappa.ipynb`.

- **5-minute step.** At 1 minute, quotes that flicker and snap back look like very fast gap closing. Pairs are rows exactly 5 minutes apart, with every minute as a start; nothing is resampled or filled in.
- **Gaps measured from each market's median.** This removes steady offsets like the election's 3¢. We also tried a trailing 24-hour median, which follows a drifting offset, but it makes c impossible to estimate: inside the band the gap wanders, the moving median follows it, and in simulations a known 3¢ band came out as 0¢.
- **Grid search for c.** For every c from 0 to 10¢ in 0.1¢ steps, κ is fitted by least squares and the c with the smallest error wins. A c is only allowed if at least 300 pairs have a gap beyond it.
- **Flagged spikes left out.** One-minute spikes flagged by the pull notebook would otherwise dominate the fit for large gaps.
- **Error bars** come from a block bootstrap: one-hour blocks are resampled 1,000 times and c and κ are refitted each time.

## First model results

| Event | c (95% range) | Half-life of the excess beyond c | Kalshi-side cost of one trade |
|---|---|---|---|
| 2024 election | 0.8¢ (0–3.0) | 34 min | 2.2¢ |
| Sept 2026 FOMC | 0.0¢ (0–0.3) | 59 min | 2.0¢ |
| Oct 2025 shutdown | 0.9¢ (0.3–2.2) | 36 min | 2.3¢ |
| Super Bowl LX | 1.2¢ (1.0–2.0) | 7 min | 2.0¢ |
| 2025 World Series | 1.3¢ (0.8–1.8) | 3.6 min | 2.4¢ |
| 2025 NBA Finals | 1.3¢ (0.8–2.3) | 5.4 min | 1.9¢ |
| 2025 papal conclave | 0.6¢ (0–0.7) | 3.9 min | 0.6¢ |
| 2025 Oscars | 1.0¢ (0–2.8) | 18 min | 2.3¢ |
| Taylor Swift engagement | 1.5¢ (0–8.9) | 2.9 h | 3.0¢ |

The Kalshi-side cost is half the Kalshi bid/ask spread plus Kalshi's fee (taken as 7% · p · (1 − p)). It's a lower bound on the cost of closing a gap, because the Polymarket side costs extra and its historical spreads aren't available.

What the validation checks found:

1. **Time step.** Politics markets and the Oscars give about the same half-life at 1, 5 and 15 minutes. In the Super Bowl and World Series the half-life keeps growing with the step: gaps close at two speeds, a fast part and a slower leftover, which a single κ can't describe.
2. **Simulation.** On fake data with known values, the method doesn't invent bands (no band → about 0¢ every time) and finds a 1¢ band 98% of the time, but wider bands only 56–64% of the time, sometimes too small. For the World Series and NBA, c comes out about 0.4–0.5¢ too low and closing looks about 2× slower than it is.
3. **c = 0 check.** The code reproduces the closed-form AR(1) results almost exactly on simulated data. Real gaps stay correlated far longer than plain mean reversion predicts.
4. **Out-of-sample prediction.** Fitted on the first 70% of each market and tested on the last 30%, the model beats a random walk in 7 of 9 markets, by 1–13%. The band beats plain mean reversion in 3 (FOMC, shutdown, World Series). It fails for the Super Bowl because the offset between the platforms drifted.

So far:
- The clearest band is in the **World Series**: c ≈ 1.3¢ with a half-life of minutes, and the band helps prediction. The simulations suggest its true band is somewhat wider.
- The **shutdown** is the only market that passes every check (c ≈ 0.9¢, half-life ≈ 36 min).
- Across markets, **c tracks Kalshi's bid/ask spread** (rank correlation +0.77), which supports reading c as a trading cost.
- **FOMC shows no band**, and for the election, papal conclave, Oscars and Taylor Swift the band's range reaches 0¢.
- The **topic comparison** is descriptive only, with three markets per topic.

## Known problems

- **Offsets drift.** Measuring gaps from each market's median handles a steady offset like the election's 3¢, but not one that moves: the Super Bowl's median gap went from +0.6¢ to −0.65¢ over its life. A drifting offset and a gap wandering inside the band look the same over long timescales, so the current model can't separate them.
- **Gaps close at two speeds.** The half-life grows with the time step in several markets, and gaps stay correlated far longer than the model predicts. One κ describes the first few minutes, not the slow leftover.
- **Estimates are biased in fast, quiet markets.** In the simulations for the World Series and NBA Finals, c comes out about 0.4–0.5¢ too low and closing looks about 2× slower than it is, because quotes often don't update minute to minute.
- **Matched points are not evenly spaced in time.** Kalshi only reports a 1-minute bar when something happens, so quiet markets have holes: up to 14 hours for the papal conclave. The fit only uses pairs exactly 5 minutes apart, so holes reduce the data but don't distort the step.
- **The papal conclave and Oscars have the least data.** About 2,700 and 3,600 matched points, against 17,000–50,000 for the others, so their estimates will be noisier.
- **Taylor Swift has the largest and most frequent gaps.** It is a real market (about 180,000 Kalshi contracts traded in the window), but it has 38 flagged points and gaps up to 22 cents, so it may behave differently from the others.
- **Some flagged points may be real.** For example, the FOMC point flagged on Sept 11 at 12:30 UTC looks like Polymarket moving on news before Kalshi. That kind of event is what the model is about, so flagged points shouldn't be dropped without a look.

## What's next

1. Extend the model to handle the two problems above: a second, slower closing rate, and an offset that's allowed to drift slowly.
2. Estimate the full round-trip cost (both platforms' spreads and fees) to compare with c. Polymarket's historical spreads aren't available, so this needs an assumption or a few days of live recording.
3. Add more events: roughly 10–20 liquid, carefully matched markets, with a written selection rule and at most one or two markets per underlying event.
4. Move the notebook logic into a proper package, with tests and CI.
