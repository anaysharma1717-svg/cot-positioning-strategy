# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A research project testing whether extreme CFTC Commitment of Traders (COT)
speculative positioning has contrarian predictive value, across three assets:
Gold (Managed Money, Disaggregated report), SPY (Leveraged Funds, TFF report),
and BTC (Leveraged Funds, TFF report). Gold is the primary result; SPY is
secondary; BTC is exploratory only (short history, thinner reporting — see
`README.md` for full rationale).

## Status

Scaffold only, unverified against live data. `fetch_cot.py` and
`fetch_prices.py` are written against the real `cot_reports`/`yfinance` APIs
but have not been run successfully yet — this environment cannot reach
cftc.gov or Yahoo Finance. `backtest.py` is intentionally left as TODOs, not
implemented — do not fill it in until `build_signal.py` output has been
visually sanity-checked.

## Commands

No test suite, linter, or build system exists yet. Run scripts directly:

```
pip install -r requirements.txt
python src/fetch_cot.py       # requires real internet access to cftc.gov
python src/fetch_prices.py    # requires real internet access (yfinance)
python src/build_signal.py    # requires parquet output from the two fetchers above
python src/backtest.py        # currently just TODOs — do not implement prematurely
```

## Pipeline architecture

The four scripts in `src/` form a strict sequential pipeline, each stage
reading the previous stage's parquet output rather than being called as a
library:

1. **`fetch_cot.py`** — pulls full COT history for two CFTC report types
   (Disaggregated for gold, TFF for SPY/BTC), filters each to the relevant
   market, and computes net speculative positioning as a % of open interest.
   Writes `data/raw/{gold,spy,btc}_positioning.parquet`.
2. **`fetch_prices.py`** — pulls daily price history per asset via yfinance.
   Writes `data/raw/{gold,spy,btc}_price.parquet`.
3. **`build_signal.py`** — for each asset, computes a rolling z-score of net
   positioning (default window: 78 weeks), then merges onto daily prices.
   Writes `data/processed/{asset}_signal.parquet`.
4. **`backtest.py`** — walk-forward backtest + block bootstrap significance
   (not yet implemented).

Follow the **build order in `README.md`** rather than jumping ahead: fetch →
inspect real column names → fetch prices → build signal → eyeball plots →
only then backtest. CFTC column names are known to be inconsistent across
report types and have changed historically, so the column names hardcoded in
`fetch_cot.py` (`M_Money_Positions_Long_All`, `Lev_Money_Positions_Long_All`,
etc.) must be confirmed against a real pull before trusting anything
downstream.

## Critical domain logic — do not simplify away

- **Look-ahead bias guard in `build_signal.py`**: the COT report date reflects
  Tuesday's positioning but isn't released until the following Friday. The
  code shifts the COT index forward 3 days before merging with price data so
  the signal is only used from its actual public release date. Any change to
  the merge logic must preserve this.
- **Report gold, SPY, and BTC separately, never pooled.** BTC's short history
  means it would dominate variance in a pooled sample despite being the
  weakest leg (see `backtest.py` TODOs and `README.md`).
- **Small effective sample size**: weekly COT data means only a handful of
  true positioning cycles per decade. Any significance testing must use a
  block bootstrap, not an in-sample Sharpe ratio.
- **Positioning can persist before it reverts** ("herding") — don't assume an
  extreme reverts immediately; test multiple hold periods and lead/lag
  structure.
- The 78-week rolling window in `build_signal.py` is a starting point, not a
  settled parameter — treat results as sensitive to it.

## Data directories

`data/raw/` and `data/processed/` are gitignored except for `.gitkeep` —
generated parquet files are never committed. `notebooks/` is for exploration
only; nothing there should be load-bearing for the pipeline.
