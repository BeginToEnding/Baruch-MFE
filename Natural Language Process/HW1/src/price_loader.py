from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from src.utils import ensure_dir


REQUIRED_PRICE_COLS = ["Date", "Close", "Volume"]


class PriceLoader:
    def __init__(self, prices_dir: str | Path, start_date: str = "2023-09-01"):
        self.prices_dir = Path(prices_dir)
        self.start_date = start_date
        ensure_dir(self.prices_dir)

    def _cache_path(self, ticker: str) -> Path:
        return self.prices_dir / f"{ticker}.parquet"

    def _normalize_price_df(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if "Date" not in out.columns:
            raise ValueError("Price dataframe must contain a Date column.")

        out["Date"] = pd.to_datetime(out["Date"]).dt.tz_localize(None).dt.normalize()

        if "Close" not in out.columns:
            raise ValueError("Price dataframe must contain a Close column.")
        out["Close"] = pd.to_numeric(out["Close"], errors="coerce")

        if "Volume" not in out.columns:
            out["Volume"] = np.nan
        out["Volume"] = pd.to_numeric(out["Volume"], errors="coerce")

        out = out[REQUIRED_PRICE_COLS].sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
        return out

    def _fetch_prices(self, ticker: str, end_date: str | None = None) -> pd.DataFrame:
        end_date = end_date or pd.Timestamp.today().strftime("%Y-%m-%d")
        raw = yf.Ticker(ticker).history(start=self.start_date, end=end_date, auto_adjust=True)
        if raw.empty:
            raise ValueError(f"No price data for ticker={ticker}")

        cols = [c for c in ["Close", "Volume"] if c in raw.columns]
        df = raw[cols].reset_index()
        df = self._normalize_price_df(df)
        df.to_parquet(self._cache_path(ticker), index=False)
        time.sleep(0.25)
        return df

    def get_or_fetch_prices(self, ticker: str, end_date: str | None = None) -> pd.DataFrame:
        cache = self._cache_path(ticker)
        if cache.exists():
            cached = pd.read_parquet(cache)
            try:
                cached = self._normalize_price_df(cached)
                if set(REQUIRED_PRICE_COLS).issubset(cached.columns):
                    return cached
            except Exception:
                pass

            try:
                return self._fetch_prices(ticker, end_date=end_date)
            except Exception:
                cached = self._normalize_price_df(cached)
                return cached

        return self._fetch_prices(ticker, end_date=end_date)

    def get_daily_return_frame(self, ticker: str, end_date: str | None = None) -> pd.DataFrame:
        df = self.get_or_fetch_prices(ticker, end_date=end_date)
        out = df.copy()
        out["daily_return"] = out["Close"].pct_change().fillna(0.0)
        return out
