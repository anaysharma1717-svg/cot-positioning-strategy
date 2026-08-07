# COT Positioning Strategy — Gold / SPY / BTC

## Idea

CFTC's weekly Commitment of Traders (COT) report shows how large speculative
players ("Managed Money" in Gold, "Leveraged Funds" in financial futures) are
positioned. When that positioning gets stretched to a historical extreme, it
has documented contrarian value — crowded positioning tends to unwind rather
than extend indefinitely.

**Signal:** z-score of net speculative positioning (long − short, as a % of
open interest) against its own trailing history, per asset. Extremes (|z| above
a threshold) generate a contrarian signal.

**Assets:**
- Gold → COMEX Gold futures, Disaggregated report, "Managed Money" category
- SPY → S&P 500 E-mini futures, Traders in Financial Futures (TFF) report,
  "Leveraged Funds" category
- BTC → CME Bitcoin futures, TFF report, "Leveraged Funds" category (shortest
  history of the three — CME BTC futures only launched in Dec 2017, and CFTC
  reporting depth is thinner than gold/SPX)

## Known limitations going in (don't skip these in the writeup)

- **Weekly data = small effective sample size.** Same issue that showed up in
  the VRP/HMM project — a handful of true positioning cycles per decade, so
  significance needs a block bootstrap, not just an in-sample Sharpe.
- **BTC leg is exploratory, not load-bearing.** Short history, thinner
  reporting. Treat gold as the primary result, SPY as secondary, BTC as a
  "does it generalize" check.
- **Positioning can persist before it reverts** ("herding"). Test lead/lag
  structure and multiple hold periods — don't assume the extreme reverts next
  week just because it's an extreme.

## Project structure

```
data/raw/          # untouched downloads (COT text/csv, raw price data)
data/processed/    # merged, resampled, feature-ready parquet files
src/
  fetch_cot.py      # pulls COT history via the `cot_reports` package
  fetch_prices.py   # pulls daily price history per asset
  build_signal.py   # merges COT + price, computes rolling z-score signal
  backtest.py       # walk-forward backtest + block bootstrap significance
notebooks/          # exploration only — nothing here should be load-bearing
```

## Status

Scaffold only. `fetch_cot.py` and `fetch_prices.py` are written against the
real library APIs but have NOT been run against live data yet — this sandbox
can't reach cftc.gov. Run these for the first time in an environment with
real internet access (see setup notes from Claude) and expect to iterate:
column names in CFTC data are notoriously fiddly and may need a small fix
once you see the actual returned DataFrame.

## Build order

1. Run `fetch_cot.py`, inspect the real columns, confirm the Managed
   Money / Leveraged Funds column names match what's used downstream.
2. Run `fetch_prices.py` for GC=F (or GLD), SPY, BTC-USD.
3. `build_signal.py` — merge on date, resample price to weekly (Tuesday,
   matching the COT report date), compute rolling z-score.
4. Eyeball plots before backtesting anything — does the z-score actually
   look mean-reverting, visually, before you trust a Sharpe number.
5. `backtest.py` — only after step 4 looks reasonable.
