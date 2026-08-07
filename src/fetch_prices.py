"""
Pull daily price history for the three assets. Needs real internet access —
run from Claude Code / your own machine, not this sandbox.
"""

import pandas as pd
import yfinance as yf

RAW_DIR = "data/raw"

TICKERS = {
    "gold": "GC=F",   # COMEX Gold futures continuous contract
    "spy": "SPY",
    "btc": "BTC-USD",
}


def fetch_prices(start: str = "2006-01-01") -> dict[str, pd.DataFrame]:
    out = {}
    for name, ticker in TICKERS.items():
        df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
        df.to_parquet(f"{RAW_DIR}/{name}_price.parquet")
        print(f"{name} ({ticker}): {len(df)} daily rows, {df.index.min()} to {df.index.max()}")
        out[name] = df
    return out


if __name__ == "__main__":
    fetch_prices()
