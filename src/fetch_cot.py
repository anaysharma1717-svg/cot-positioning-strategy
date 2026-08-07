"""
Pull CFTC Commitment of Traders history for the three assets in this project.

Requires real internet access to cftc.gov — will NOT run in a network-sandboxed
environment. Run this from Claude Code (or your own machine) after `pip install
-r requirements.txt`.

Gold uses the Disaggregated report ("Managed Money" category).
SPY (via S&P 500 E-mini futures) and BTC (via CME Bitcoin futures) use the
Traders in Financial Futures report ("Leveraged Funds" category) — this is
the closest TFF analog to "Managed Money" in the Disaggregated report.

NOTE: this has been written against the real cot_reports API (verified via
inspect/help on the installed package) but NOT run against live data yet.
Column names in CFTC's raw files are known to be finicky — after your first
successful pull, print(df.columns.tolist()) and confirm the Managed
Money / Leveraged Funds column names below still match before trusting
downstream results.
"""

import numpy as np
import pandas as pd
import cot_reports as cot

RAW_DIR = "data/raw"

# Exact market names as they appear in Market_and_Exchange_Names — verified
# against a live pull on 2026-08-07. CFTC's naming is inconsistent across
# report types and has changed wording historically, so re-confirm if a
# fetch starts returning 0 rows for one of these.
GOLD_MARKET_NAME = "GOLD - COMMODITY EXCHANGE INC."
SP500_MARKET_NAME = "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE"
BTC_MARKET_NAME = "BITCOIN - CHICAGO MERCANTILE EXCHANGE"


def _coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    CFTC's raw data mixes real ints with whitespace-padded numeric strings
    (e.g. '    251') across the years the underlying text-file format
    changed, and uses '.' as a placeholder for suppressed/confidential
    values. That leaves many columns as object dtype with mixed int/str
    content, which pyarrow refuses to write to parquet.

    Strip whitespace and treat '.' as missing, then coerce a column to
    numeric only if every remaining value parses cleanly AND none carry a
    leading zero (guards against silently truncating zero-padded identifier
    columns like CFTC_Contract_Market_Code, e.g. '001602' -> 1602). Some
    years also format whole numbers with a trailing '.0' (e.g. '-12868.0')
    instead of as plain ints, so integrality is checked on the parsed value
    rather than by string round-trip. Columns that don't satisfy both are
    left untouched as strings.
    """
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        stripped = df[col].astype(str).str.strip().replace(".", np.nan)
        is_null = df[col].isna() | stripped.isna()
        numeric = pd.to_numeric(stripped, errors="coerce")
        if (numeric.isna() & ~is_null).any():
            continue
        if stripped[~is_null].str.match(r"^-?0\d").any():
            continue
        if (numeric[~is_null] % 1 == 0).all():
            df[col] = numeric.astype("Int64")
        else:
            df[col] = numeric.astype("float64")
    return df


def fetch_disaggregated() -> pd.DataFrame:
    """Full history of the Disaggregated Futures Only report (Gold lives here)."""
    df = cot.cot_all(cot_report_type="disaggregated_fut", store_txt=False, verbose=True)
    df = _coerce_numeric_columns(df)
    df.to_parquet(f"{RAW_DIR}/disaggregated_fut_all.parquet")
    return df


def fetch_tff() -> pd.DataFrame:
    """Full history of the Traders in Financial Futures report (SPY, BTC live here)."""
    df = cot.cot_all(
        cot_report_type="traders_in_financial_futures_fut", store_txt=False, verbose=True
    )
    df = _coerce_numeric_columns(df)
    df.to_parquet(f"{RAW_DIR}/tff_fut_all.parquet")
    return df


def extract_gold(disagg_df: pd.DataFrame) -> pd.DataFrame:
    """Filter to Gold and compute net Managed Money positioning."""
    # Exact match, not substring: Market_and_Exchange_Names also contains
    # "MICRO GOLD - COMMODITY EXCHANGE INC." and "GOLD -1 TROY OUNCE  -
    # COINBASE DERIVATIVES, LLC" — a substring match on "GOLD" silently
    # mixes three unrelated contracts into one series.
    g = disagg_df[disagg_df["Market_and_Exchange_Names"] == GOLD_MARKET_NAME].copy()
    g["net_mm"] = g["M_Money_Positions_Long_All"] - g["M_Money_Positions_Short_All"]
    g["net_mm_pct_oi"] = g["net_mm"] / g["Open_Interest_All"]
    g["report_date"] = pd.to_datetime(g["Report_Date_as_YYYY-MM-DD"])
    return g[["report_date", "net_mm", "net_mm_pct_oi", "Open_Interest_All"]].sort_values(
        "report_date"
    )


def extract_leveraged(tff_df: pd.DataFrame, market_name: str) -> pd.DataFrame:
    """Filter TFF report to one exact market and compute net Leveraged Funds positioning."""
    # Exact match, not substring: e.g. "S&P 500" also matches "S&P 500
    # Consolidated", "MICRO E-MINI S&P 500 INDEX", dividend/total-return
    # index futures, etc. — 9 unrelated contracts for S&P 500 alone, 7 for
    # "BITCOIN" (including a Bitcoin Cash contract on a different exchange).
    m = tff_df[tff_df["Market_and_Exchange_Names"] == market_name].copy()
    m["net_lev"] = m["Lev_Money_Positions_Long_All"] - m["Lev_Money_Positions_Short_All"]
    m["net_lev_pct_oi"] = m["net_lev"] / m["Open_Interest_All"]
    m["report_date"] = pd.to_datetime(m["Report_Date_as_YYYY-MM-DD"])
    return m[["report_date", "net_lev", "net_lev_pct_oi", "Open_Interest_All"]].sort_values(
        "report_date"
    )


if __name__ == "__main__":
    disagg = fetch_disaggregated()
    tff = fetch_tff()

    gold = extract_gold(disagg)
    gold.to_parquet(f"{RAW_DIR}/gold_positioning.parquet")
    print(f"Gold: {len(gold)} weekly rows, {gold['report_date'].min()} to {gold['report_date'].max()}")

    spy = extract_leveraged(tff, SP500_MARKET_NAME)
    spy.to_parquet(f"{RAW_DIR}/spy_positioning.parquet")
    print(f"SPY:  {len(spy)} weekly rows, {spy['report_date'].min()} to {spy['report_date'].max()}")

    btc = extract_leveraged(tff, BTC_MARKET_NAME)
    btc.to_parquet(f"{RAW_DIR}/btc_positioning.parquet")
    print(f"BTC:  {len(btc)} weekly rows, {btc['report_date'].min()} to {btc['report_date'].max()}")
