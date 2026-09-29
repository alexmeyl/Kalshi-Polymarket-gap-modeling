"""
Pilot pull: Kalshi vs. Polymarket price history for one matched event.

Usage (two-step, because you need real ticker/token IDs first):

    STEP 1 — find the identifiers
    ------------------------------
    python pilot_pull.py find-kalshi KXFEDDECISION
    python pilot_pull.py find-polymarket fed-decision-in-december-2024

    This prints candidate markets/tokens so you can pick the exact ticker
    (Kalshi) and token_id (Polymarket) for the event you want.

    STEP 2 — pull, align, and plot
    -------------------------------
    python pilot_pull.py pull \
        --kalshi-ticker KXFEDDECISION-24DEC-C25 \
        --poly-token-id 102369396088772761357240590665759663791718757290813171305408958759381342090613 \
        --start 2024-11-01 --end 2024-12-20 \
        --out fomc_dec2024

Outputs (in ./out/<label>/):
    kalshi.csv, polymarket.csv, gap.csv, gap_plot.png

Requires: requests, pandas, matplotlib
    pip install requests pandas matplotlib
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
# Some Kalshi deployments use this host instead; if the above 404s, try:
KALSHI_BASE_ALT = "https://trading-api.kalshi.com/trade-api/v2"

POLY_GAMMA_BASE = "https://gamma-api.polymarket.com"
POLY_CLOB_BASE = "https://clob.polymarket.com"


# --------------------------------------------------------------------------
# Step 1 helpers: find the right ticker / token id
# --------------------------------------------------------------------------

def find_kalshi_markets(series_ticker: str) -> pd.DataFrame:
    """List markets in a Kalshi series so you can pick the exact settled ticker."""
    url = f"{KALSHI_BASE}/markets"
    params = {"series_ticker": series_ticker, "limit": 200}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    markets = r.json().get("markets", [])
    if not markets:
        print(f"No markets found for series {series_ticker}. "
              f"Double check the series ticker on the Kalshi market page URL.")
        return pd.DataFrame()
    df = pd.DataFrame(markets)
    cols = [c for c in ["ticker", "title", "status", "close_time", "result"] if c in df.columns]
    return df[cols]


def find_polymarket_event(slug_or_query: str) -> pd.DataFrame:
    """
    Look up a Polymarket event by slug (as it appears in the URL,
    e.g. polymarket.com/event/<slug>) and list its markets + CLOB token ids.
    """
    url = f"{POLY_GAMMA_BASE}/events"
    params = {"slug": slug_or_query}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    events = r.json()
    if not events:
        # fall back to a text search
        r = requests.get(url, params={"search": slug_or_query}, timeout=20)
        r.raise_for_status()
        events = r.json()
    rows = []
    for ev in events:
        for m in ev.get("markets", []):
            rows.append({
                "event_slug": ev.get("slug"),
                "market_question": m.get("question"),
                "clob_token_ids": m.get("clobTokenIds"),
                "closed": m.get("closed"),
                "end_date": m.get("endDate"),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        print(f"No Polymarket event found for '{slug_or_query}'. "
              f"Check the slug in the event's URL.")
    return df


# --------------------------------------------------------------------------
# Step 2 helpers: pull actual price history
# --------------------------------------------------------------------------

def to_unix(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def get_kalshi_candles(ticker: str, start: str, end: str, period_minutes: int = 60) -> pd.DataFrame:
    """
    Pull Kalshi candlesticks for a single market ticker.
    Tries the live endpoint first, falls back to the historical endpoint
    (settled markets before Kalshi's rolling cutoff live only there).
    """
    start_ts, end_ts = to_unix(start), to_unix(end)
    params = {
        "start_ts": start_ts,
        "end_ts": end_ts,
        "period_interval": period_minutes,
    }

    for base in (KALSHI_BASE, KALSHI_BASE_ALT):
        for path in (f"/markets/{ticker}/candlesticks", f"/historical/markets/{ticker}/candlesticks"):
            try:
                r = requests.get(f"{base}{path}", params=params, timeout=20)
                if r.status_code == 200:
                    candles = r.json().get("candlesticks", [])
                    if candles:
                        df = pd.json_normalize(candles)
                        df["timestamp"] = pd.to_datetime(df["end_period_ts"], unit="s", utc=True)
                        df["price"] = df["price.close_dollars"].astype(float)
                        return df[["timestamp", "price", "volume_fp"]].rename(
                            columns={"volume_fp": "volume"}
                        )
            except requests.RequestException:
                continue
    print(f"WARNING: no Kalshi candles returned for ticker {ticker} in [{start}, {end}]. "
          f"Ticker may be wrong, or this market predates the candlestick archive.")
    return pd.DataFrame(columns=["timestamp", "price", "volume"])


def get_polymarket_history(token_id: str, start: str, end: str, fidelity_minutes: int = 60) -> pd.DataFrame:
    """Pull Polymarket CLOB price history for a single token id."""
    start_ts, end_ts = to_unix(start), to_unix(end)
    params = {
        "market": token_id,
        "startTs": start_ts,
        "endTs": end_ts,
        "fidelity": fidelity_minutes,
    }
    r = requests.get(f"{POLY_CLOB_BASE}/prices-history", params=params, timeout=20)
    r.raise_for_status()
    history = r.json().get("history", [])
    if not history:
        print(f"WARNING: no Polymarket history returned for token {token_id} in [{start}, {end}]. "
              f"This is a known failure mode for some older tokens -- verify the token id via "
              f"find-polymarket first, and try interval='max' with no start/end as a fallback.")
        return pd.DataFrame(columns=["timestamp", "price"])
    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["t"], unit="s", utc=True)
    df["price"] = df["p"].astype(float)
    return df[["timestamp", "price"]]


def align_and_gap(kalshi_df: pd.DataFrame, poly_df: pd.DataFrame, freq: str = "1H") -> pd.DataFrame:
    """Resample both series to a common grid and compute the gap G(t) = Kalshi - Polymarket."""
    if kalshi_df.empty or poly_df.empty:
        print("Cannot align: one or both series are empty.")
        return pd.DataFrame()

    k = kalshi_df.set_index("timestamp")["price"].resample(freq).ffill()
    p = poly_df.set_index("timestamp")["price"].resample(freq).ffill()

    merged = pd.concat([k.rename("kalshi"), p.rename("polymarket")], axis=1).dropna()
    merged["gap"] = merged["kalshi"] - merged["polymarket"]
    return merged.reset_index()


def plot_gap(merged: pd.DataFrame, out_path: Path, title: str) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    axes[0].plot(merged["timestamp"], merged["kalshi"], label="Kalshi")
    axes[0].plot(merged["timestamp"], merged["polymarket"], label="Polymarket")
    axes[0].set_ylabel("Implied probability")
    axes[0].legend()
    axes[0].set_title(title)

    axes[1].plot(merged["timestamp"], merged["gap"], color="black")
    axes[1].axhline(0, color="gray", linewidth=0.8)
    axes[1].set_ylabel("Gap (Kalshi - Poly)")
    axes[1].set_xlabel("Time (UTC)")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved plot to {out_path}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fk = sub.add_parser("find-kalshi", help="List markets in a Kalshi series")
    p_fk.add_argument("series_ticker")

    p_fp = sub.add_parser("find-polymarket", help="Look up a Polymarket event's markets and token ids")
    p_fp.add_argument("slug_or_query")

    p_pull = sub.add_parser("pull", help="Pull, align, and plot both series")
    p_pull.add_argument("--kalshi-ticker", required=True)
    p_pull.add_argument("--poly-token-id", required=True)
    p_pull.add_argument("--start", required=True, help="YYYY-MM-DD")
    p_pull.add_argument("--end", required=True, help="YYYY-MM-DD")
    p_pull.add_argument("--freq", default="1H", help="pandas resample freq, e.g. 1H, 15min")
    p_pull.add_argument("--out", required=True, help="label for output files, e.g. fomc_dec2024")

    args = parser.parse_args()

    if args.command == "find-kalshi":
        df = find_kalshi_markets(args.series_ticker)
        if not df.empty:
            print(df.to_string(index=False))

    elif args.command == "find-polymarket":
        df = find_polymarket_event(args.slug_or_query)
        if not df.empty:
            print(df.to_string(index=False))

    elif args.command == "pull":
        out_dir = Path("out") / args.out
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"Pulling Kalshi ticker {args.kalshi_ticker} ...")
        kalshi_df = get_kalshi_candles(args.kalshi_ticker, args.start, args.end)
        kalshi_df.to_csv(out_dir / "kalshi.csv", index=False)

        print(f"Pulling Polymarket token {args.poly_token_id} ...")
        poly_df = get_polymarket_history(args.poly_token_id, args.start, args.end)
        poly_df.to_csv(out_dir / "polymarket.csv", index=False)

        merged = align_and_gap(kalshi_df, poly_df, freq=args.freq)
        if merged.empty:
            print("No aligned data to plot. Check the warnings above.")
            sys.exit(1)

        merged.to_csv(out_dir / "gap.csv", index=False)
        plot_gap(merged, out_dir / "gap_plot.png", title=args.out)

        print(f"\nDone. n={len(merged)} aligned points, "
              f"mean|gap|={merged['gap'].abs().mean():.4f}, "
              f"max|gap|={merged['gap'].abs().max():.4f}")


if __name__ == "__main__":
    main()
