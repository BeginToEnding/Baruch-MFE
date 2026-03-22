import argparse
import os
import sys
from typing import Optional

import joblib
import pandas as pd

from feature_engineering import EST_VOL_COL, run_mode1_feature_generation


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Feature generation and model application CLI."
    )

    parser.add_argument(
        "-i",
        "--input-dir",
        required=True,
        help="Input directory. For Mode 1, root folder containing data_daily/ and data_intraday/. For Mode 2, interpretation is defined by the chosen mode.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        required=True,
        help="Output directory. For Mode 1, where feature CSVs will be written. For Mode 2, interpretation is defined by the chosen mode.",
    )
    parser.add_argument(
        "-p",
        "--model-dir",
        required=False,
        help="Directory containing learned model(s). Required in Mode 2.",
    )
    parser.add_argument(
        "-s",
        "--start-date",
        required=True,
        help="Start date in YYYYMMDD format.",
    )
    parser.add_argument(
        "-e",
        "--end-date",
        required=True,
        help="End date in YYYYMMDD format.",
    )
    parser.add_argument(
        "-m",
        "--mode",
        required=True,
        type=int,
        choices=[1, 2],
        help="Processing mode. 1 = feature generation, 2 = apply model (requires -p).",
    )

    return parser.parse_args(argv)


def run_mode1(args: argparse.Namespace) -> None:
    """Mode 1: feature generation using raw data."""
    run_mode1_feature_generation(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        normalize_features=True,
    )


def run_mode2(model_dir: str, input_dir: str, output_dir: str, start_date: str, end_date: str) -> None:
    """
    Run mode 2 prediction.
    :param model_dir: Directory containing the model.
    :param input_dir: Directory containing the features.
    :param output_dir: Directory to save the predictions.
    :param start_date: Start date in YYYYMMDD format.
    :param end_date: End date in YYYYMMDD format.
    :return: None
    :Load the model from the model_dir.
    Load the features from the input_dir.
    Make predictions and save the results to the output_dir.
    """
    if not model_dir:
        raise ValueError("Mode 2 requires -p / --model-dir to be specified.")

    os.makedirs(output_dir, exist_ok=True)

    model = joblib.load(os.path.join(model_dir, "final_model.pkl"))

    features = []
    for fn in os.listdir(input_dir):
        if fn.endswith(".csv"):
            # Files are named like 20260318.csv, so we need to check the date
            date_str = fn[:8]
            if date_str >= start_date and date_str <= end_date:
                features.append(pd.read_csv(os.path.join(input_dir, fn)))
            else:
                continue
    if len(features) == 0:
        raise ValueError(f"No features found for dates {start_date} to {end_date}")
    
    features = pd.concat(features)
    features.sort_values(by=["Date", "ID"], inplace=True)
    
    NON_FEATURE_COLS = ["Date", "ID", "EST_VOL", "MDV_63"]
    non_features_df = features[NON_FEATURE_COLS]

    # Should be in same order as the model was trained on
    FEATURE_COLS = sorted([c for c in features.columns if c not in NON_FEATURE_COLS])
    features = features[FEATURE_COLS]

    pred_te_norm = model.predict(features)
    y_pred = pred_te_norm * non_features_df[EST_VOL_COL].values

    COLUMNS_TO_SAVE = ["Date", "Time", "ID","Pred"]
    predictions_df = non_features_df.copy()
    predictions_df["Time"] = "15:30:00.000"
    predictions_df["Pred"] = y_pred
    for date in predictions_df["Date"].unique():
        date_str = pd.to_datetime(date).strftime("%Y%m%d")
        predictions_df_date = predictions_df[predictions_df["Date"] == date]
        predictions_df_date[COLUMNS_TO_SAVE].to_csv(os.path.join(output_dir, f"{date_str}.csv"), index=False)
        print(f"[mode2] saved predictions for {date_str}: ({len(predictions_df_date)} rows)")


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)

    if args.mode == 1:
        run_mode1(args)
    elif args.mode == 2:
        run_mode2(args.model_dir, args.input_dir, args.output_dir, args.start_date, args.end_date)
    else:
        raise ValueError(f"Unsupported mode: {args.mode}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

