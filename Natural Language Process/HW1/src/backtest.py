from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def _signal_multiplier(cfg: dict) -> float:
    return 1.0 if bool(cfg.get("greater_is_better", True)) else -1.0


def _benchmark_return_col(cfg: dict) -> str:
    return str(cfg["benchmark_return_col"])


def _benchmark_cum_return_col(cfg: dict) -> str:
    return _benchmark_return_col(cfg).replace("_return", "_cum_return")


def _benchmark_daily_return_col(cfg: dict) -> str:
    return _benchmark_return_col(cfg).replace("_return", "_daily_return")


def _annualization_days(cfg: dict) -> int:
    return int(cfg.get("annualization_days", TRADING_DAYS_PER_YEAR))


def _signal_series(df: pd.DataFrame, cfg: dict) -> pd.Series:
    signal_col = str(cfg.get("signal_col", "y_pred"))
    if signal_col not in df.columns:
        raise ValueError(f"signal_col={signal_col} not found in prediction dataframe.")
    return _signal_multiplier(cfg) * pd.to_numeric(df[signal_col], errors="coerce")


def _build_trade_table(df_pred: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = df_pred.copy()
    long_thr = float(cfg.get("long_threshold", 0.0))
    short_thr = float(cfg.get("short_threshold", 0.0))

    df["signal_score"] = _signal_series(df, cfg)
    df["position"] = 0
    df.loc[df["signal_score"] > long_thr, "position"] = 1
    df.loc[df["signal_score"] < short_thr, "position"] = -1

    df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.normalize()
    df["exit_date"] = pd.to_datetime(df["exit_date"]).dt.normalize()
    df["call_date"] = pd.to_datetime(df["call_date"]).dt.normalize()

    return df.sort_values(["entry_date", "ticker"]).reset_index(drop=True)


def _build_trade_return_ledger(
    trade_df: pd.DataFrame,
    price_map: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows = []
    for _, trade in trade_df.iterrows():
        ticker = str(trade["ticker"])
        position = int(trade["position"])
        entry_date = trade["entry_date"]
        exit_date = trade["exit_date"]

        if position == 0 or pd.isna(entry_date) or pd.isna(exit_date):
            continue
        if ticker not in price_map:
            continue
        
        px = price_map[ticker].copy()
        px["Date"] = pd.to_datetime(px["Date"]).dt.normalize()
        px = px.sort_values("Date").reset_index(drop=True)
        px["daily_return"] = pd.to_numeric(px["daily_return"], errors="coerce").fillna(0.0)

        active = px.loc[(px["Date"] > entry_date) & (px["Date"] <= exit_date), ["Date", "daily_return"]].copy()
        if active.empty:
            continue

        active["ticker"] = ticker
        active["call_date"] = trade["call_date"]
        active["entry_date"] = entry_date
        active["exit_date"] = exit_date
        active["position"] = position
        active["pnl_component"] = position * active["daily_return"]
        rows.append(active)

    if not rows:
        return pd.DataFrame(
            columns=[
                "Date", "ticker", "call_date", "entry_date", "exit_date",
                "position", "daily_return", "pnl_component",
            ]
        )

    return pd.concat(rows, ignore_index=True)


def _aggregate_daily_strategy_returns(
    trade_ledger: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    cfg: dict,
) -> pd.DataFrame:
    benchmark = benchmark_df.copy()
    benchmark["Date"] = pd.to_datetime(benchmark["Date"]).dt.normalize()
    benchmark = benchmark.sort_values("Date").reset_index(drop=True)
    benchmark_daily_col = _benchmark_daily_return_col(cfg)
    benchmark[benchmark_daily_col] = pd.to_numeric(benchmark["daily_return"], errors="coerce").fillna(0.0)
    
    if trade_ledger.empty:
        out = benchmark[["Date", benchmark_daily_col]].copy()
        out["gross_exposure"] = 0.0
        out["n_active_positions"] = 0
        out["strategy_return"] = 0.0
        out["cum_return"] = 0.0
        out[_benchmark_cum_return_col(cfg)] = (1.0 + out[benchmark_daily_col]).cumprod() - 1.0
        return out

    start_date = pd.to_datetime(trade_ledger["Date"]).min().normalize()
    end_date = pd.to_datetime(trade_ledger["Date"]).max().normalize()
    benchmark = benchmark.loc[(benchmark["Date"] >= start_date) & (benchmark["Date"] <= end_date)].copy()

    daily = (
        trade_ledger.groupby("Date", as_index=False)
        .agg(
            pnl_sum=("pnl_component", "sum"),
            gross_exposure=("position", lambda s: float(np.abs(s).sum())),
            n_active_positions=("ticker", "count"),
        )
    )

    out = benchmark[["Date", benchmark_daily_col]].merge(daily, on="Date", how="left")
    out["gross_exposure"] = out["gross_exposure"].fillna(0.0)
    out["n_active_positions"] = out["n_active_positions"].fillna(0).astype(int)
    out["pnl_sum"] = out["pnl_sum"].fillna(0.0)
    out["strategy_return"] = np.where(
        out["gross_exposure"] > 0,
        out["pnl_sum"] / out["gross_exposure"],
        0.0,
    )
    out["cum_return"] = (1.0 + out["strategy_return"]).cumprod() - 1.0
    out[_benchmark_cum_return_col(cfg)] = (1.0 + out[benchmark_daily_col]).cumprod() - 1.0
    return out.drop(columns=["pnl_sum"])


def _compute_trade_metrics(trade_df: pd.DataFrame) -> tuple[float, float, int]:
    traded = trade_df.loc[trade_df["position"] != 0, ["signal_score", "y_true", "position"]].dropna().copy()
    if traded.empty:
        return 0.0, 0.0, 0
    
    directional_accuracy = float(((traded["position"] * traded["y_true"]) > 0).mean())
    if len(traded) >= 2:
        information_coefficient = float(traded["signal_score"].corr(traded["y_true"], method="spearman"))
    else:
        information_coefficient = 0.0
    return directional_accuracy, information_coefficient, int(len(traded))


def _compute_daily_summary(
    daily_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    cfg: dict,
) -> dict:
    active_df = daily_df.loc[daily_df["gross_exposure"] > 0].copy()
    annualization_days = _annualization_days(cfg)
    benchmark_daily_col = _benchmark_daily_return_col(cfg)

    if active_df.empty:
        directional_accuracy, information_coefficient, n_trades = _compute_trade_metrics(trade_df)
        return {
            "mean_return": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "hit_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "directional_accuracy": directional_accuracy,
            "information_coefficient": information_coefficient,
            "n_trades": n_trades,
            "n_active_days": 0,
            "benchmark_mean_return": 0.0,
        }

    ret = active_df["strategy_return"]
    mean_daily = float(ret.mean())
    vol_daily = float(ret.std(ddof=0))

    annualized_mean = mean_daily * annualization_days
    annualized_vol = vol_daily * np.sqrt(annualization_days)
    sharpe = 0.0 if annualized_vol == 0 else annualized_mean / annualized_vol

    wins = ret[ret > 0]
    losses = ret[ret < 0]

    directional_accuracy, information_coefficient, n_trades = _compute_trade_metrics(trade_df)

    return {
        "mean_return": float(annualized_mean),
        "volatility": float(annualized_vol),
        "sharpe": float(sharpe),
        "hit_rate": float((ret < 0).mean()),
        "avg_win": float(wins.mean()) if not wins.empty else 0.0,
        "avg_loss": float(losses.mean()) if not losses.empty else 0.0,
        "directional_accuracy": float(directional_accuracy),
        "information_coefficient": float(information_coefficient),
        "n_trades": n_trades,
        "n_active_days": int(len(active_df)),
        "benchmark_mean_return": float(active_df[benchmark_daily_col].mean() * annualization_days),
    }


def run_event_backtest(
    df_pred: pd.DataFrame,
    price_map: dict[str, pd.DataFrame],
    benchmark_df: pd.DataFrame,
    cfg: dict,
) -> tuple[pd.DataFrame, dict]:
    trade_df = _build_trade_table(df_pred, cfg)
    trade_ledger = _build_trade_return_ledger(trade_df, price_map)
    daily_df = _aggregate_daily_strategy_returns(trade_ledger, benchmark_df, cfg)
    summary = _compute_daily_summary(daily_df, trade_df, cfg)
    return daily_df, summary


def save_backtest_plot(
    curve_map: dict[str, pd.DataFrame],
    out_path: str | Path,
    ret_col: str = "cum_return",
    title: str = "Backtest Curve",
    benchmark_name: str = "benchmark",
    benchmark_cum_return_col: str = "benchmark_cum_return",
) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(9, 5))
    benchmark_plotted = False

    for label, df in curve_map.items():
        if df.empty or ret_col not in df.columns:
            continue

        x = pd.to_datetime(df["Date"]) if "Date" in df.columns else range(len(df))
        plt.plot(x, df[ret_col], label=label)

        if (
            not benchmark_plotted
            and benchmark_cum_return_col in df.columns
            and df[benchmark_cum_return_col].notna().any()
        ):
            plt.plot(x, df[benchmark_cum_return_col], label=benchmark_name, linestyle="--", color="black")
            benchmark_plotted = True

    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
