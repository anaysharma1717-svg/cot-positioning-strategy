"""
Merge weekly COT positioning with daily price data and build the z-score
signal. Run only after fetch_cot.py and fetch_prices.py have produced real
parquet files in data/raw/.
"""

import pandas as pd

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"

ASSETS = {
    "gold": {"cot_col": "net_mm_pct_oi", "cot_file": "gold_positioning.parquet", "price_file": "gold_price.parquet"},
    "spy": {"cot_col": "net_lev_pct_oi", "cot_file": "spy_positioning.parquet", "price_file": "spy_price.parquet"},
    "btc": {"cot_col": "net_lev_pct_oi", "cot_file": "btc_positioning.parquet", "price_file": "btc_price.parquet"},
}


def build_zscore_signal(asset: str, window: int = 78) -> pd.DataFrame:
    """
    window=78 weeks (~1.5 years) is a starting point, not a settled choice —
    test sensitivity to window length before trusting any single result.
    """
    cfg = ASSETS[asset]
    cot = pd.read_parquet(f"{RAW_DIR}/{cfg['cot_file']}")
    price = pd.read_parquet(f"{RAW_DIR}/{cfg['price_file']}")

    cot = cot.set_index("report_date").sort_index()
    cot["z"] = (
        cot[cfg["cot_col"]] - cot[cfg["cot_col"]].rolling(window).mean()
    ) / cot[cfg["cot_col"]].rolling(window).std()

    # COT report reflects Tuesday's positioning, released the following Friday.
    # Shift forward so the signal is only usable from the actual release date —
    # using the Tuesday date directly would leak information you couldn't have
    # traded on yet.
    cot.index = cot.index + pd.Timedelta(days=3)

    price = price.sort_index()
    merged = price.join(cot[["z", cfg["cot_col"]]], how="left").ffill()
    merged = merged.dropna(subset=["z"])

    merged.to_parquet(f"{PROCESSED_DIR}/{asset}_signal.parquet")
    return merged


if __name__ == "__main__":
    for asset in ASSETS:
        df = build_zscore_signal(asset)
        print(f"{asset}: {len(df)} rows, z range [{df['z'].min():.2f}, {df['z'].max():.2f}]")
