from __future__ import annotations

from pathlib import Path

import pandas as pd
from tqdm import tqdm

from src.backtest import run_event_backtest, save_backtest_plot
from src.extractor import Extractor
from src.features import EXTERNAL_SIGNAL_COLS, build_features
from src.model_report import generate_full_model_report
from src.models import (
    build_model_frames,
    check_model_target_compatibility,
    evaluate_predictions,
    fit_logistic_clf_predict,
    fit_rf_clf_predict,
    fit_rf_reg_predict,
    fit_ridge_reg_predict,
    fit_xgb_clf_predict,
    fit_xgb_reg_predict,
)
from src.price_loader import PriceLoader
from src.speaker_labeling import add_speaker_labels
from src.split import build_time_split
from src.target_builder import build_targets
from src.transcript_parser import TranscriptParser
from src.utils import (
    ensure_dir,
    load_yaml,
    read_json,
    read_parquet,
    setup_logger,
    write_json,
    write_parquet,
)


def _paths(cfg: dict) -> dict:
    return cfg["project"]


def _benchmark_return_col(cfg: dict) -> str:
    benchmark = str(cfg.get("price", {}).get("benchmark", "SPY")).strip()
    if not benchmark:
        benchmark = "benchmark"
    return f"{benchmark.lower()}_return"


def _backtest_cfg(cfg: dict) -> dict:
    out = dict(cfg["backtest"])
    out["benchmark_name"] = cfg.get("price", {}).get("benchmark", "benchmark")
    out["benchmark_return_col"] = _benchmark_return_col(cfg)
    out["benchmark_cum_return_col"] = _benchmark_return_col(cfg).replace("_return", "_cum_return")
    return out


def _target_name(cfg: dict) -> str:
    if cfg["target"].get("use_classification", False):
        return "y_class"
    if cfg["target"].get("use_excess", False):
        return "y_excess"
    return "y_raw"


def _variant_specs(cfg: dict) -> list[dict]:
    use_external = bool(cfg.get("feature", {}).get("use_external_signals", False))
    if not use_external:
        return [{"feature_set": "nlp_only", "exclude_extra": []}]

    nlp_feature_exclude = list(EXTERNAL_SIGNAL_COLS)
    external_only_exclude = [
        "overall_sentiment_score",
        "ceo_cfo_consistency",
        "analyst_sentiment_score",
        "reactive_sentiment_score",
        "guidance_net_score",
        "reactive_topic_ratio",
        "avg_risk_sentiment",
        "risk_persistence_ratio",
        "new_risk_flag",
        "sentiment_delta",
        "guidance_delta",
        "new_theme_ratio",
    ]

    return [
        {"feature_set": "nlp_only", "exclude_extra": nlp_feature_exclude},
        {"feature_set": "external_only", "exclude_extra": external_only_exclude},
        {"feature_set": "nlp_plus_external", "exclude_extra": []},
    ]


def _prediction_filename(model_name: str, feature_set: str, compare_variants: bool) -> str:
    if compare_variants:
        return f"{model_name}_{feature_set}_predictions.parquet"
    return f"{model_name}_predictions.parquet"


def _prediction_paths_for_model(cfg: dict, model_name: str) -> list[tuple[str, Path]]:
    predictions_dir = Path(_paths(cfg)["predictions_dir"])
    compare_variants = bool(cfg.get("feature", {}).get("use_external_signals", False))
    paths = []
    for spec in _variant_specs(cfg):
        feature_set = spec["feature_set"]
        path = predictions_dir / _prediction_filename(model_name, feature_set, compare_variants)
        if path.exists():
            paths.append((feature_set, path))
    return paths


def _output_dirs_for_model(cfg: dict, model_name: str) -> tuple[Path, Path]:
    p = _paths(cfg)
    table_dir = ensure_dir(Path(p["outputs_tables_dir"]) / model_name)
    figure_dir = ensure_dir(Path(p["outputs_figures_dir"]) / model_name)
    return table_dir, figure_dir


def parse_stage(cfg: dict, logger):
    p = _paths(cfg)
    parser = TranscriptParser()
    transcript_dir = Path(p["transcripts_dir"])
    parsed_dir = ensure_dir(p["parsed_dir"])

    n_files = 0
    for fp in sorted(transcript_dir.glob("*.txt")):
        record = parser.parse_file(fp)
        record = add_speaker_labels(record)
        out_path = parsed_dir / f"{fp.stem}.json"
        write_json(record, out_path)
        n_files += 1

    logger.info("Parsed %d transcripts.", n_files)


def extract_stage(cfg: dict, logger):
    p = cfg["project"]
    llm_cfg = cfg["llm"]
    prompt_cfg = load_yaml("config/prompts.yaml")
    extractor = Extractor(llm_cfg, prompt_cfg, p["extraction_raw_dir"], p["extraction_json_dir"])

    parsed_dir = Path(p["parsed_dir"])
    files = sorted(parsed_dir.glob("*.json"))

    for fp in tqdm(files, desc="Extracting transcripts", unit="file"):
        record = read_json(fp)
        extractor.extract_unified(record)

    logger.info("Extracted structured JSON for %d transcripts.", len(files))


def features_stage(cfg: dict, logger):
    p = _paths(cfg)

    feature_df = build_features(
        p["extraction_json_dir"],
        prices_dir=p["prices_dir"],
        price_cfg=cfg["price"],
        feature_cfg=cfg.get("feature", {}),
    )
    if feature_df.empty:
        raise ValueError("No extracted unified JSON found. Run extract stage first.")

    logger.info("Built features for %d records.", len(feature_df))

    target_df = build_targets(feature_df, p["prices_dir"], cfg["price"], cfg["target"])
    logger.info("Built targets for %d records.", len(target_df))

    modeling_df = feature_df.merge(target_df, on=["ticker", "quarter", "call_date"], how="left")
    modeling_df = build_time_split(modeling_df, int(cfg["split"]["n_train_per_ticker"]))
    logger.info("Built modeling table with %d records.", len(modeling_df))

    write_parquet(feature_df, Path(p["processed_dir"]) / "features.parquet")
    write_parquet(modeling_df, Path(p["processed_dir"]) / "modeling_table.parquet")
    write_parquet(
        modeling_df[["ticker", "quarter", "call_date", "split"]],
        Path(p["processed_dir"]) / "split_table.parquet",
    )

    logger.info("Saved features and modeling table with %d rows.", len(modeling_df))


def _fit_model(
    model_name: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: list[str],
    target_name: str,
    model_cfg: dict,
) -> pd.DataFrame:
    if model_name == "ridge_reg":
        _, pred_df = fit_ridge_reg_predict(train_df, test_df, feature_cols, target_name, model_cfg)
    elif model_name == "rf_reg":
        _, pred_df = fit_rf_reg_predict(train_df, test_df, feature_cols, target_name, model_cfg)
    elif model_name == "xgb_reg":
        _, pred_df = fit_xgb_reg_predict(train_df, test_df, feature_cols, target_name, model_cfg)
    elif model_name == "logistic_clf":
        _, pred_df = fit_logistic_clf_predict(train_df, test_df, feature_cols, target_name, model_cfg)
    elif model_name == "rf_clf":
        _, pred_df = fit_rf_clf_predict(train_df, test_df, feature_cols, target_name, model_cfg)
    elif model_name == "xgb_clf":
        _, pred_df = fit_xgb_clf_predict(train_df, test_df, feature_cols, target_name, model_cfg)
    else:
        raise ValueError(f"Unsupported model_name={model_name}")
    return pred_df


def model_stage(cfg: dict, logger, model_name: str):
    p = _paths(cfg)
    modeling_df = read_parquet(Path(p["processed_dir"]) / "modeling_table.parquet")
    target_name = _target_name(cfg)

    check_model_target_compatibility(model_name, target_name)
    compare_variants = bool(cfg.get("feature", {}).get("use_external_signals", False))

    metrics_rows = []
    for spec in _variant_specs(cfg):
        feature_set = spec["feature_set"]
        exclude = list(cfg["model"]["feature_exclude"]) + list(spec["exclude_extra"])

        train_df, test_df, feature_cols = build_model_frames(
            modeling_df,
            target_name=target_name,
            exclude=exclude,
            retain_benchmark_return=bool(cfg["model"].get("retain_benchmark_return", False)),
            benchmark_return_col=_benchmark_return_col(cfg),
        )

        model_cfg = dict(cfg["model"][model_name])
        model_cfg["benchmark_return_col"] = _benchmark_return_col(cfg)

        pred_df = _fit_model(model_name, train_df, test_df, feature_cols, target_name, model_cfg)
        pred_df["feature_set"] = feature_set
        pred_df["prediction_name"] = f"{model_name}_{feature_set}" if compare_variants else model_name

        out_path = Path(p["predictions_dir"]) / _prediction_filename(model_name, feature_set, compare_variants)
        write_parquet(pred_df, out_path)

        metrics = evaluate_predictions(pred_df)
        metrics["model_name"] = model_name
        metrics["feature_set"] = feature_set
        metrics["prediction_name"] = pred_df["prediction_name"].iloc[0]
        metrics["target_name"] = target_name
        metrics["n_features"] = len(feature_cols)
        metrics_rows.append(metrics)

        logger.info("Saved predictions to %s using feature_set=%s", out_path, feature_set)

    table_dir, _ = _output_dirs_for_model(cfg, model_name)
    pd.DataFrame(metrics_rows).to_csv(table_dir / "model_metrics.csv", index=False)


def _load_price_inputs_for_predictions(
    cfg: dict,
    prediction_dfs: list[pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    p = _paths(cfg)
    loader = PriceLoader(
        prices_dir=p["prices_dir"],
        start_date=cfg["price"].get("start_date", "2023-09-01"),
    )

    tickers = sorted(
        {
            str(ticker)
            for df in prediction_dfs
            for ticker in df["ticker"].dropna().unique().tolist()
        }
    )
    price_map = {ticker: loader.get_daily_return_frame(ticker) for ticker in tickers}
    benchmark_df = loader.get_daily_return_frame(cfg["price"].get("benchmark", "SPY"))
    return price_map, benchmark_df


def backtest_stage(cfg: dict, logger, prediction_path: str, model_name: str):
    if prediction_path:
        prediction_specs = [("custom", Path(prediction_path))]
    else:
        prediction_specs = _prediction_paths_for_model(cfg, model_name)
        if not prediction_specs:
            default_path = Path(_paths(cfg)["predictions_dir"]) / f"{model_name}_predictions.parquet"
            if default_path.exists():
                prediction_specs = [("nlp_only", default_path)]

    if not prediction_specs:
        raise ValueError(f"No prediction files found for model={model_name}. Run model stage first.")

    prediction_dfs = []
    curve_map = {}
    detail_rows = []
    summary_rows = []

    for _, path in prediction_specs:
        prediction_dfs.append(read_parquet(path))

    price_map, benchmark_df = _load_price_inputs_for_predictions(cfg, prediction_dfs)
    bt_cfg = _backtest_cfg(cfg)

    for (_, path), df_pred in zip(prediction_specs, prediction_dfs):
        label = str(df_pred.get("prediction_name", pd.Series([path.stem])).iloc[0])
        feature_set = str(df_pred.get("feature_set", pd.Series(["nlp_only"])).iloc[0])

        bt_df, summary = run_event_backtest(df_pred, price_map=price_map, benchmark_df=benchmark_df, cfg=bt_cfg)
        bt_df = bt_df.copy()
        bt_df["model_name"] = model_name
        bt_df["feature_set"] = feature_set
        bt_df["prediction_name"] = label

        summary_rows.append({"model_name": model_name, "feature_set": feature_set, "prediction_name": label, **summary})
        detail_rows.append(bt_df)
        curve_map[label] = bt_df

    table_dir, figure_dir = _output_dirs_for_model(cfg, model_name)
    detail_df = pd.concat(detail_rows, ignore_index=True) if detail_rows else pd.DataFrame()
    summary_df = pd.DataFrame(summary_rows)

    detail_df.to_csv(table_dir / "backtest_detail.csv", index=False)
    summary_df.to_csv(table_dir / "backtest_summary.csv", index=False)

    save_backtest_plot(
        curve_map,
        figure_dir / "event_equity_curve.png",
        ret_col="cum_return",
        title=f"Event Backtest: {model_name}",
        benchmark_name=bt_cfg["benchmark_name"],
        benchmark_cum_return_col=bt_cfg["benchmark_cum_return_col"],
    )

    logger.info("Saved backtest outputs to %s and %s", table_dir, figure_dir)


def report_stage(cfg: dict, logger):
    p = _paths(cfg)
    predictions_dir = Path(p["predictions_dir"])
    report_dir = Path(p["outputs_reports_dir"]) / "model_report"
    ensure_dir(report_dir)

    prediction_files = {}
    for fp in sorted(predictions_dir.glob("*_predictions.parquet")):
        if "external_only" in fp.stem:
            continue
        prediction_files[fp.stem.replace("_predictions", "")] = str(fp)

    if not prediction_files:
        raise ValueError(f"No prediction parquet files found in {predictions_dir}. Run model stage first.")

    logger.info("Found prediction files for models: %s", ", ".join(prediction_files.keys()))

    loader = PriceLoader(
        prices_dir=p["prices_dir"],
        start_date=cfg["price"].get("start_date", "2023-09-01"),
    )
    pred_map = [read_parquet(path) for path in prediction_files.values()]
    tickers = sorted({str(t) for df in pred_map for t in df["ticker"].dropna().unique().tolist()})
    price_map = {ticker: loader.get_daily_return_frame(ticker) for ticker in tickers}
    benchmark_df = loader.get_daily_return_frame(cfg["price"].get("benchmark", "SPY"))

    generate_full_model_report(
        prediction_files=prediction_files,
        event_cfg=_backtest_cfg(cfg),
        output_dir=report_dir,
        price_map=price_map,
        benchmark_df=benchmark_df,
    )

    logger.info("Saved model comparison report to %s", report_dir)


def run_stage(stage: str, config_path: str, model_name: str = "ridge_reg", prediction_path: str = ""):
    cfg = load_yaml(config_path)
    logger = setup_logger(cfg["project"]["log_path"])

    if stage == "parse":
        parse_stage(cfg, logger)
    elif stage == "extract":
        extract_stage(cfg, logger)
    elif stage == "features":
        features_stage(cfg, logger)
    elif stage == "model":
        model_stage(cfg, logger, model_name)
    elif stage == "backtest":
        backtest_stage(cfg, logger, prediction_path, model_name)
    elif stage == "report":
        report_stage(cfg, logger)
    elif stage == "train":
        model_stage(cfg, logger, model_name)
        backtest_stage(cfg, logger, prediction_path, model_name)
    elif stage == "all":
        parse_stage(cfg, logger)
        extract_stage(cfg, logger)
        features_stage(cfg, logger)
        model_stage(cfg, logger, model_name)
        backtest_stage(cfg, logger, prediction_path, model_name)
    else:
        raise ValueError(f"Unknown stage={stage}")
