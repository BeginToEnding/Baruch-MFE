from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.backtest import run_event_backtest
from src.utils import ensure_dir, read_parquet


def directional_accuracy(df: pd.DataFrame) -> float:
    tmp = df[["y_true", "y_pred"]].dropna().copy()
    if tmp.empty:
        return 0.0
    return float(((tmp["y_true"] * tmp["y_pred"]) > 0).mean())


def information_coefficient(df: pd.DataFrame) -> float:
    tmp = df[["y_true", "y_pred"]].dropna().copy()
    if len(tmp) < 2:
        return 0.0
    return float(tmp["y_true"].corr(tmp["y_pred"], method="spearman"))


def regression_summary(df: pd.DataFrame) -> dict:
    tmp = df[["y_true", "y_pred"]].dropna().copy()
    feature_set = str(df.get("feature_set", pd.Series(["nlp_only"])).iloc[0])
    prediction_name = str(df.get("prediction_name", pd.Series(["unknown"])).iloc[0])

    if tmp.empty:
        return {
            "feature_set": feature_set,
            "prediction_name": prediction_name,
            "n_obs": 0,
            "directional_accuracy": 0.0,
            "information_coefficient": 0.0,
            "mean_y_pred": 0.0,
            "std_y_pred": 0.0,
            "mean_y_true": 0.0,
            "std_y_true": 0.0,
        }

    return {
        "feature_set": feature_set,
        "prediction_name": prediction_name,
        "n_obs": int(len(tmp)),
        "directional_accuracy": directional_accuracy(tmp),
        "information_coefficient": information_coefficient(tmp),
        "mean_y_pred": float(tmp["y_pred"].mean()),
        "std_y_pred": float(tmp["y_pred"].std(ddof=0)),
        "mean_y_true": float(tmp["y_true"].mean()),
        "std_y_true": float(tmp["y_true"].std(ddof=0)),
    }


def load_prediction_dict(prediction_files: dict[str, str]) -> dict[str, pd.DataFrame]:
    return {label: read_parquet(path) for label, path in prediction_files.items()}


def build_model_comparison_table(prediction_files: dict[str, str]) -> pd.DataFrame:
    pred_map = load_prediction_dict(prediction_files)
    rows = []
    for label, df in pred_map.items():
        row = {"model_key": label}
        row.update(regression_summary(df))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("information_coefficient", ascending=False)


def build_backtest_table(
    prediction_files: dict[str, str],
    event_cfg: dict,
    price_map: dict[str, pd.DataFrame],
    benchmark_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    pred_map = load_prediction_dict(prediction_files)
    rows = []
    curves = {}

    for label, df in pred_map.items():
        curve_df, summary = run_event_backtest(df, price_map=price_map, benchmark_df=benchmark_df, cfg=event_cfg)
        summary = {
            "model_key": label,
            "feature_set": str(df.get("feature_set", pd.Series(["nlp_only"])).iloc[0]),
            "prediction_name": str(df.get("prediction_name", pd.Series([label])).iloc[0]),
            **summary,
        }
        rows.append(summary)
        curves[label] = curve_df

    return pd.DataFrame(rows), curves


def plot_equity_curves(
    curve_map: dict[str, pd.DataFrame],
    out_path: str | Path,
    y_col: str = "cum_return",
    title: str = "Equity Curves",
    benchmark_name: str = "benchmark",
    benchmark_cum_return_col: str = "benchmark_cum_return",
) -> None:
    out_path = Path(out_path)
    ensure_dir(out_path.parent)

    plt.figure(figsize=(9, 5))
    benchmark_plotted = False

    for label, df in curve_map.items():
        if df.empty or y_col not in df.columns:
            continue

        x = pd.to_datetime(df["Date"]) if "Date" in df.columns else range(len(df))
        plt.plot(x, df[y_col], label=label)

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


def plot_prediction_scatter_grid(
    prediction_files: dict[str, str],
    out_path: str | Path,
) -> None:
    pred_map = load_prediction_dict(prediction_files)
    labels = list(pred_map.keys())
    n = len(labels)
    if n == 0:
        return

    out_path = Path(out_path)
    ensure_dir(out_path.parent)

    fig, axes = plt.subplots(n, 1, figsize=(6, 4 * n))
    if n == 1:
        axes = [axes]

    for ax, label in zip(axes, labels):
        df = pred_map[label][["y_true", "y_pred"]].dropna()
        ax.scatter(df["y_pred"], df["y_true"], alpha=0.7)
        ax.set_title(label)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Realized")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_ic_bar(summary_df: pd.DataFrame, out_path: str | Path) -> None:
    out_path = Path(out_path)
    ensure_dir(out_path.parent)

    plt.figure(figsize=(7, 4))
    x = range(len(summary_df))
    plt.bar(x, summary_df["information_coefficient"])
    plt.xticks(x, summary_df["model_key"], rotation=20)
    plt.title("Model Information Coefficient")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def generate_full_model_report(
    prediction_files: dict[str, str],
    event_cfg: dict,
    output_dir: str | Path,
    price_map: dict[str, pd.DataFrame],
    benchmark_df: pd.DataFrame,
) -> None:
    output_dir = Path(output_dir)
    ensure_dir(output_dir)

    comparison_df = build_model_comparison_table(prediction_files)
    comparison_df.to_csv(output_dir / "model_comparison_summary.csv", index=False)

    event_table, event_curves = build_backtest_table(
        prediction_files,
        event_cfg=event_cfg,
        price_map=price_map,
        benchmark_df=benchmark_df,
    )
    event_table.to_csv(output_dir / "model_event_backtest_summary.csv", index=False)

    plot_equity_curves(
        event_curves,
        output_dir / "model_event_equity_curves.png",
        y_col="cum_return",
        title="Event Backtest Comparison",
        benchmark_name=event_cfg["benchmark_name"],
        benchmark_cum_return_col=event_cfg["benchmark_cum_return_col"],
    )

    plot_prediction_scatter_grid(prediction_files, output_dir / "model_prediction_scatter.png")
    plot_ic_bar(comparison_df, output_dir / "model_ic_bar.png")
