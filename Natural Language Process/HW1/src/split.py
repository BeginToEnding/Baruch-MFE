from __future__ import annotations
import pandas as pd

def build_time_split(df: pd.DataFrame, n_train_per_ticker: int) -> pd.DataFrame:
    df = df.sort_values(["ticker", "call_date"]).copy()
    df["seq"] = df.groupby("ticker").cumcount() + 1
    df["split"] = df.groupby("ticker")["seq"].transform(lambda s: ["train" if i <= n_train_per_ticker else "test" for i in s])
    return df.drop(columns=["seq"])
