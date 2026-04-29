from __future__ import annotations
import argparse
from src.pipeline import run_stage

def parse_args():
    parser = argparse.ArgumentParser(description="Earnings call project pipeline")
    parser.add_argument("--stage", required=True, choices=["parse", "extract", "features", "model", "backtest", "report", "train", "all"])
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--model_name", default="ridge_reg")
    parser.add_argument("--prediction_path", default="")
    return parser.parse_args()

def main():
    args = parse_args()
    run_stage(stage=args.stage, config_path=args.config, model_name=args.model_name, prediction_path=args.prediction_path)

if __name__ == "__main__":
    main()
