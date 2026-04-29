from __future__ import annotations
import pandas as pd
from src.utils import next_trading_day
from src.price_loader import PriceLoader


def _benchmark_return_col(price_cfg: dict) -> str:
    benchmark = str(price_cfg.get("benchmark", "SPY")).strip()
    if not benchmark:
        benchmark = "benchmark"
    return f"{benchmark.lower()}_return"


def _compute_forward_return(
    price_df: pd.DataFrame,
    call_date,
    window_size: int,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None, float | None]:
    price_df = price_df.copy()
    price_df["Date"] = pd.to_datetime(price_df["Date"]).dt.normalize()
    call_date = pd.to_datetime(call_date).normalize()
    
    entry_date = next_trading_day(price_df["Date"], call_date)
    if entry_date is None:
        return None, None, None

    price_df = price_df.sort_values("Date").reset_index(drop=True)
    idx = price_df.index[price_df["Date"] == entry_date]
    if len(idx) == 0:
        return None, None, None

    idx = int(idx[0])
    exit_idx = idx + window_size

    # Not enough future data: keep entry_date, but mark exit/return missing
    if exit_idx >= len(price_df):
        return entry_date, None, None

    entry_px = float(price_df.loc[idx, "Close"])
    exit_px = float(price_df.loc[exit_idx, "Close"])
    exit_date = pd.Timestamp(price_df.loc[exit_idx, "Date"]).normalize()

    if entry_px <= 0:
        return entry_date, exit_date, None

    ret = exit_px / entry_px - 1.0
    return entry_date, exit_date, ret


def build_targets(
    feature_df: pd.DataFrame,
    prices_dir: str,
    price_cfg: dict,
    target_cfg: dict,
) -> pd.DataFrame:
    loader = PriceLoader(
        prices_dir=prices_dir,
        start_date=price_cfg.get("start_date", "2023-09-01"),
    )

    benchmark = price_cfg.get("benchmark", "SPY")
    benchmark_return_col = _benchmark_return_col(price_cfg)
    bench_df = loader.get_or_fetch_prices(benchmark)

    rows = []
    window_size = int(target_cfg["window_size"])

    for _, row in feature_df.iterrows():
        ticker = row["ticker"]
        call_date = pd.to_datetime(row["call_date"]).normalize()

        stock_df = loader.get_or_fetch_prices(ticker)

        entry_date, exit_date, y_raw = _compute_forward_return(
            stock_df, call_date, window_size
        )
        _, _, bmk_ret = _compute_forward_return(
            bench_df, call_date, window_size
        )

        y_excess = None if (y_raw is None or bmk_ret is None) else (y_raw - bmk_ret)

        rows.append(
            {
                "ticker": ticker,
                "quarter": row["quarter"],
                "call_date": call_date,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "y_raw": y_raw,
                benchmark_return_col: bmk_ret,
                "y_excess": y_excess,
            }
        )

    out = pd.DataFrame(rows)

    metric_col = "y_excess" if target_cfg.get("use_excess", False) else "y_raw"

    if target_cfg.get("use_classification", False):
        up_thr = float(target_cfg.get("classification_up_threshold", 0.01))
        down_thr = float(target_cfg.get("classification_down_threshold", -0.01))

        def _classify_three_way_numeric(x):
            if pd.isna(x):
                return None
            if x >= up_thr:
                return 1
            if x <= down_thr:
                return -1
            return 0

        def _classify_three_way_label(x):
            if pd.isna(x):
                return None
            if x >= up_thr:
                return "up"
            if x <= down_thr:
                return "down"
            return "flat"

        out["y_class"] = out[metric_col].apply(_classify_three_way_numeric)
        out["y_class_label"] = out[metric_col].apply(_classify_three_way_label)
    else:
        out["y_class"] = None
        out["y_class_label"] = None

    return out
