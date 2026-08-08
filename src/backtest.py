"""
Backtest the COT positioning contrarian signal, with block bootstrap
significance testing on the resulting Sharpe ratio.

Design notes:
- The z-score itself (from build_signal.py) is already computed causally --
  each row's z uses only its own trailing 78-week window and is merged onto
  prices via merge_asof(direction="backward"), so it never sees the future.
  There is no separate "fit" step here to walk forward over; ENTRY_THRESHOLDS
  is a small sensitivity grid (per the README's own "1.5-2.0, test
  sensitivity" note), not a parameter tuned on this data.
- Contrarian direction: enter short when z > entry_z (positioning crowded
  long -> bet price falls), long when z < -entry_z (crowded short -> bet
  price rises).
- Both exit rules from the README are implemented and reported separately
  ("revert toward zero" vs. "max holding period") since they imply different
  mechanisms, not blended into one rule.
- Strategy return on day t uses position decided at the close of day t-1
  (position.shift(1)) times day t's price return, so a decision can only
  earn a return that happens after it was made.
- Significance: circular block bootstrap (blocks wrap around the series) on
  daily strategy returns. Blocking preserves the autocorrelation daily
  returns actually have, unlike an i.i.d. bootstrap. Two variants:
  demeaned-returns resampling for a null-hypothesis p-value (H0: true mean
  return is 0), and real-returns resampling for a 90% CI on the Sharpe
  estimate itself.
- Reported per-asset, never pooled -- BTC's short history would dominate
  variance in a combined sample despite being the weakest leg.
"""

import numpy as np
import pandas as pd

PROCESSED_DIR = "data/processed"

ASSETS = ["gold", "spy", "btc"]
ENTRY_THRESHOLDS = [1.5, 2.0]
EXIT_MODES = ["revert", "max_hold"]
EXIT_Z = 0.5           # "reverted toward zero" band used by the revert exit
MAX_HOLD_DAYS = 20      # ~1 trading month, used by the max_hold exit
N_BOOTSTRAP = 2000
BLOCK_LEN = 20          # ~1 trading month, long enough to span short return-autocorrelation
TRADING_DAYS_PER_YEAR = 252


def build_positions(z: pd.Series, entry_z: float, exit_mode: str) -> pd.Series:
    """Contrarian state machine: flat -> short/long on entry, back to flat on exit."""
    z_vals = z.to_numpy()
    position = np.zeros(len(z_vals), dtype=int)
    state = 0
    days_held = 0
    for i in range(len(z_vals)):
        zi = z_vals[i]
        if state == 0:
            if zi > entry_z:
                state = -1
                days_held = 0
            elif zi < -entry_z:
                state = 1
                days_held = 0
        else:
            days_held += 1
            if exit_mode == "revert":
                if abs(zi) < EXIT_Z:
                    state = 0
            else:  # max_hold
                if days_held >= MAX_HOLD_DAYS:
                    state = 0
        position[i] = state
    return pd.Series(position, index=z.index)


def sharpe(returns: pd.Series) -> float:
    returns = returns.dropna()
    if len(returns) == 0 or returns.std() == 0:
        return np.nan
    return returns.mean() / returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)


def circular_block_bootstrap_sharpe(returns: np.ndarray, block_len: int, n_boot: int, demean: bool, rng: np.random.Generator) -> np.ndarray:
    n = len(returns)
    if demean:
        returns = returns - returns.mean()
    n_blocks = int(np.ceil(n / block_len))
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    offsets = np.arange(block_len)
    idx = (starts[:, :, None] + offsets[None, None, :]) % n
    samples = returns[idx].reshape(n_boot, -1)[:, :n]
    means = samples.mean(axis=1)
    stds = samples.std(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        boot_sharpes = np.where(stds > 0, means / stds * np.sqrt(TRADING_DAYS_PER_YEAR), np.nan)
    return boot_sharpes


def run_backtest(asset: str, rng: np.random.Generator) -> list[dict]:
    df = pd.read_parquet(f"{PROCESSED_DIR}/{asset}_signal.parquet").sort_index()
    asset_return = df["Close"].pct_change()
    buy_hold_sharpe = sharpe(asset_return)

    results = []
    for entry_z in ENTRY_THRESHOLDS:
        for exit_mode in EXIT_MODES:
            position = build_positions(df["z"], entry_z, exit_mode)
            strat_return = (position.shift(1).fillna(0) * asset_return).dropna()
            n_entries = int(((position != 0) & (position.shift(1).fillna(0) == 0)).sum())

            strat_sharpe = sharpe(strat_return)
            returns_arr = strat_return.to_numpy()

            null_boot = circular_block_bootstrap_sharpe(returns_arr, BLOCK_LEN, N_BOOTSTRAP, demean=True, rng=rng)
            p_value = np.nanmean(np.abs(null_boot) >= abs(strat_sharpe)) if not np.isnan(strat_sharpe) else np.nan

            ci_boot = circular_block_bootstrap_sharpe(returns_arr, BLOCK_LEN, N_BOOTSTRAP, demean=False, rng=rng)
            ci_low, ci_high = np.nanpercentile(ci_boot, [5, 95])

            results.append({
                "asset": asset,
                "entry_z": entry_z,
                "exit_mode": exit_mode,
                "n_entries": n_entries,
                "pct_time_in_market": float((position != 0).mean()),
                "strategy_sharpe": strat_sharpe,
                "sharpe_ci_5": ci_low,
                "sharpe_ci_95": ci_high,
                "bootstrap_p_value": p_value,
                "buy_hold_sharpe": buy_hold_sharpe,
            })
    return results


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    all_results = []
    for asset in ASSETS:
        asset_results = run_backtest(asset, rng)
        all_results.extend(asset_results)

        print(f"===== {asset} =====")
        print(f"buy-and-hold Sharpe: {asset_results[0]['buy_hold_sharpe']:.2f}")
        for r in asset_results:
            print(
                f"  entry|z|>{r['entry_z']}, exit={r['exit_mode']:9s} | "
                f"n_entries={r['n_entries']:4d}  time-in-mkt={r['pct_time_in_market']*100:4.0f}%  "
                f"Sharpe={r['strategy_sharpe']:6.2f}  90% CI=[{r['sharpe_ci_5']:6.2f}, {r['sharpe_ci_95']:6.2f}]  "
                f"p={r['bootstrap_p_value']:.3f}"
            )
        print()

    pd.DataFrame(all_results).to_csv(f"{PROCESSED_DIR}/backtest_results.csv", index=False)
