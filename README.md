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

## Where the project stands

**Done:** data collection for nine events at 1-minute resolution, cleaned of settlement artifacts and aligned into a gap series for each.
**Not done yet:** handling persistent offsets, fitting the model, error bars, the c = 0 check, and the baseline comparison. See [What's next](#whats-next).

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
results/
  summary.csv              # one row per event
  <event>/gap.csv          # aligned prices and the gap, with outlier flags
  <event>/gap_plot.png     # prices on top, gap below
pilot_pull.py, FOMC.ipynb  # early one-event experiments, superseded by the notebook
```

The notebook writes to a folder called `out/`. The `results/` folder in this repo is a saved copy of one run of that notebook.

## How to run it

1. Open `notebook/pull_all_events.ipynb` in Jupyter or Google Colab.
2. Run it top to bottom (about 2 minutes). It needs `requests`, `pandas`, and `matplotlib`. No API keys are needed, since both platforms' price endpoints are public.
3. Outputs appear in `out/`. Check the `status` column of `out/summary.csv`: it says `ok` unless a download failed.

The settings at the top of the notebook control the bar size (`BAR_MINUTES`, default 1; set 60 for hourly), the Kalshi spread filter, and the outlier flag. The `EVENTS` list holds each event's Kalshi ticker, Polymarket token ID, and date range. An event marked `FILL_IN` is skipped.

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

## Known problems

- **The 2024 election has a constant offset.** Polymarket sat about 3 cents above Kalshi throughout (mean gap −0.032). That's a steady bias, not a gap closing, and a threshold model could mistake it for a large c unless it's handled.
- **Matched points are not evenly spaced in time.** Kalshi only reports a 1-minute bar when something happens, so quiet markets have holes: up to 14 hours for the papal conclave. The `dt_minutes` column gives the spacing. The model's "t+1" needs a consistent definition before fitting.
- **The papal conclave and Oscars have the least data.** About 2,700 and 3,600 matched points, against 17,000–50,000 for the others, so their estimates will be noisier.
- **Taylor Swift has the largest and most frequent gaps.** It is a real market (about 180,000 Kalshi contracts traded in the window), but it has 38 flagged points and gaps up to 22 cents, so it may behave differently from the others.
- **Some flagged points may be real.** For example, the FOMC point flagged on Sept 11 at 12:30 UTC looks like Polymarket moving on news before Kalshi. That kind of event is what the model is about, so flagged points shouldn't be dropped without a look.

## What's next

1. Decide how to handle persistent offsets like the election's.
2. Decide how to define "t+1" given the uneven spacing.
3. Fit κ and c per event, then pool across events.
4. Get error bars with a bootstrap.
5. Check the c = 0 case against the closed-form mean-reversion result.
6. Compare against a simple baseline model.
7. Move the notebook logic into a proper package, with tests and CI.
