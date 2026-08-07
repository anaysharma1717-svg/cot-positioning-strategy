"""
Backtest skeleton — deliberately left as structure + TODOs.

Do not fill this in until build_signal.py output has been visually checked
(plot z vs. forward returns) and cointegration/mean-reversion behavior looks
plausible. Backtesting a signal you haven't sanity-checked just produces a
confident-looking number with no diagnostic value if it's wrong.

TODO, in order:
1. Load data/processed/{asset}_signal.parquet
2. Define entry/exit rule: enter contrarian position when |z| > threshold
   (start with 1.5-2.0), exit on z reverting toward 0 or after a max holding
   period (test both, they imply different things about the mechanism)
3. Walk-forward, not a single in-sample fit — refit the rolling window
   parameters only on data available at that point in time
4. Compare against a naive baseline (buy-and-hold, or a simple trend-following
   baseline) — a mean-reversion strategy that just underperforms buy-and-hold
   in a trending asset (esp. BTC) is not "working," even with a positive Sharpe
5. Block bootstrap significance test on the resulting Sharpe (same method used
   in the VRP project) before drawing any conclusion — expect this to matter
   given how few genuine positioning cycles exist per asset
6. Report gold, SPY, and BTC separately — do not average across assets into
   one headline number, since BTC's short history means it will dominate
   variance in a pooled sample despite being the weakest leg
"""

# import pandas as pd
# import numpy as np

PROCESSED_DIR = "data/processed"
