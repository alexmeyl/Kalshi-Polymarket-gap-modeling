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

**Done:** data collection for nine events, aligned into a gap series for each.
**Not done yet:** cleaning the data, fitting the model, error bars, the c = 0 check, and the baseline comparison. See [What's next](#whats-next).

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
notebooks/
  pull_all_events.ipynb    # downloads, aligns, and plots everything
results/
  summary.csv              # one row per event
  <event>/gap.csv          # aligned prices and the gap, with outlier flags
  <event>/gap_plot.png     # prices on top, gap below
```

The notebook writes to a folder called `out/`. The `results/` folder in this repo is a saved copy of one run of that notebook.

## How to run it

1. Open `notebooks/pull_all_events.ipynb` in Jupyter or Google Colab.
2. Run it top to bottom. It needs `requests`, `pandas`, and `matplotlib`. No API keys are needed, since both platforms' price endpoints are public.
3. Outputs appear in `out/`.

The `EVENTS` list in the notebook holds each event's Kalshi ticker, Polymarket token ID, and date range. An event marked `FILL_IN` is skipped.

## How the data is pulled

A few decisions worth knowing about, because most of them came from something breaking:

- **Kalshi has two tiers.** Recent markets are served by the live API, and older ones by a separate `/historical/` API with different URLs and field names. The notebook detects which tier a ticker is in and parses each format.
- **Both platforms cap request size.** Kalshi allows at most 5,000 candles per request, and Polymarket about two weeks. Long ranges are downloaded in chunks.
- **Polymarket needs the right endpoint.** The older `clob.polymarket.com` history endpoint only gives 12-hour resolution for closed markets. The `data-api.polymarket.com/v2/prices-history` endpoint gives much finer data.
- **The two series are never resampled or forward-filled.** Doing that creates a fake lag between the platforms. Instead, each Polymarket point is matched to the nearest Kalshi point within a 45-minute window, and points with no match are dropped.
- **Outliers are flagged, not deleted.** A point is flagged when it sits far from the median of its neighbors, measured with the median absolute deviation so that one big spike can't hide itself. The flag means "looks structurally unusual," not "confirmed bad."

## What the raw data shows so far

These numbers are unfiltered, straight from `results/summary.csv`.

| Event | Matched points | Mean abs gap | Max abs gap |
|---|---|---|---|
| 2024 election | 609 | 0.028 | 0.067 |
| Sept 2026 FOMC | 778 | 0.011 | 0.410 |
| Oct 2025 shutdown | 362 | 0.022 | 0.140 |
| Super Bowl LX | 925 | 0.008 | 0.500 |
| 2025 World Series | 765 | 0.012 | 0.500 |
| 2025 NBA Finals | 802 | 0.007 | 0.505 |
| 2025 papal conclave | 244 | 0.006 | 0.500 |
| 2025 Oscars | 511 | 0.018 | 0.050 |
| Taylor Swift engagement | 947 | 0.029 | 0.500 |

Prices are implied probabilities from 0 to 1, so a gap of 0.01 is one cent.

## Known problems

- **Some gaps are probably bad data.** In most events the max gap is about 0.5, while the typical gap is around a cent. A 50-point gap is almost certainly a bad candle, not a real disagreement. These points need a proper filter before any model is fit.
- **The 2024 election has a constant offset.** Polymarket sat about 3 cents above Kalshi throughout (mean gap −0.028). That's a steady bias, not a gap closing, and a threshold model could mistake it for a large c unless it's handled.
- **Taylor Swift may be a thin market.** An earlier check showed no volume on Kalshi, yet the pull returns about 950 points. Its volume needs checking before we trust it.
- **The papal event has the least data.** Its 244 matched points are well below the 500–950 for the others, so its estimates will be noisier.
- **Matched points are not evenly spaced in time.** The model's "t+1" needs a consistent definition before fitting.

## What's next

1. Filter the bad-candle points and document the rule.
2. Decide how to handle persistent offsets like the election's.
3. Fit κ and c per event, then pool across events.
4. Get error bars with a bootstrap.
5. Check the c = 0 case against the closed-form mean-reversion result.
6. Compare against a simple baseline model.
7. Move the notebook logic into a proper package, with tests and CI.