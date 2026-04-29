# Assignment 1: Earnings Call NLP Pipeline

This repository implements an end-to-end pipeline for turning raw earnings call transcripts into structured signals, model predictions, and daily portfolio backtests. The project is organized as a sequence of stages:

1. Parse raw transcript text into a clean structured representation.
2. Ask an LLM to extract sentiment, guidance, wins, risks, and topic-level information.
3. Convert the extracted JSON into numeric features.
4. Align those features with forward stock returns and benchmark-adjusted targets.
5. Train a predictive model on the earlier calls for each ticker.
6. Save predictions and evaluate them with a daily event-driven backtest that supports overlapping holdings.
7. Generate comparison tables and plots across saved model outputs.

The current command-line entry point is [main.py](/C:/Users/Lenovo/Desktop/Baruch/MFE/2026Spring/Natural%20Language%20Process/HW1/main.py:1), and most of the logic lives in `src/`.

## Repository Layout

`data/raw/transcripts/`
Raw earnings call text files. Each file is expected to be named like `AMD_Q3-2025.txt`.

`data/interim/parsed/`
Parsed transcript JSON after speaker segmentation and Q&A detection.

`data/interim/extraction_raw/`
Raw model responses from the LLM extraction step.

`data/interim/extraction_json/`
Validated structured JSON used for feature engineering.

`data/interim/prices/`
Cached market data used for target construction.

`data/processed/`
Feature tables and the final modeling table.

`data/predictions/`
Saved prediction parquet files, one per model.

`outputs/tables/`, `outputs/figures/`, `outputs/reports/`
Metrics, plots, and model comparison reports. Backtest stage outputs are now saved under model-specific subfolders such as `outputs/tables/ridge_reg/`.

`config/default.yaml`
Main experiment configuration.

`config/prompts.yaml`
System prompt and few-shot examples for extraction.

`project walkthrough.ipynb`
A presentation-style notebook for inspecting saved feature tables, predictions, and report outputs. It is intended as a guided walkthrough of the project artifacts rather than the main execution entry point.

## Environment Setup

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

If you use the OpenAI API, create a `.env` file with your API key. The code expects standard environment-variable based authentication.

The default configuration currently uses:

- OpenAI as the extraction provider
- `gpt-5.4-mini` as the extraction model
- `SPY` as the benchmark
- `y_excess` as the default prediction target
- the first 6 calls per ticker as training data
- optional external price-volume signals controlled from `feature.use_external_signals`

## How To Run

Run the full pipeline:

```bash
python main.py --stage all --config config/default.yaml --model_name ridge_reg
```

Run one stage at a time:

```bash
python main.py --stage parse
python main.py --stage extract
python main.py --stage features
python main.py --stage model --model_name ridge_reg
python main.py --stage backtest --model_name ridge_reg
python main.py --stage report
```

If you want a quick visual walkthrough of the saved intermediate outputs after running the pipeline, open `project walkthrough.ipynb`.

Train and backtest a single model in one command:

```bash
python main.py --stage train --model_name xgb_reg
```

Backtest a specific saved prediction file:

```bash
python main.py --stage backtest --model_name ridge_reg --prediction_path data/predictions/ridge_reg_predictions.parquet
```

## Pipeline Stages

### 1. `parse`

This stage reads each transcript text file, detects metadata and dialogue structure, labels speaker roles, and saves one parsed JSON per call.

Input:
- `data/raw/transcripts/*.txt`

Output:
- `data/interim/parsed/*.json`

### 2. `extract`

This stage loads each parsed transcript, builds a structured prompt, sends it to the LLM, saves the raw completion, validates the response, and saves a normalized JSON object.

Input:
- `data/interim/parsed/*.json`

Output:
- `data/interim/extraction_raw/*`
- `data/interim/extraction_json/*_unified.json`

### 3. `features`

This stage converts extraction JSON into numeric features, optionally adds external price-volume signals, computes forward returns and benchmark-adjusted targets, and builds the final modeling table.

Input:
- `data/interim/extraction_json/*.json`
- market prices from `data/interim/prices/`

Output:
- `data/processed/features.parquet`
- `data/processed/modeling_table.parquet`
- `data/processed/split_table.parquet`

Important:
If you change anything that affects the target `y`, you must rerun the `features` stage before training again. This includes changes to:

- `target.window_size`
- `target.use_excess`
- `target.use_classification`
- `target.classification_up_threshold`
- `target.classification_down_threshold`
- `price.benchmark`

Those settings change how `y_raw`, `y_excess`, or `y_class` are constructed, so previously saved modeling tables and predictions are no longer valid after such edits.

### 4. `model`

This stage selects a target, filters numeric features, keeps benchmark returns if configured, trains the requested model on the train split, predicts on the test split, and saves the test prediction dataframe.

If `feature.use_external_signals: true`, the model stage automatically runs three variants:

- ``nlp_only``
- `external_only`
- `nlp_plus_external`

Input:
- `data/processed/modeling_table.parquet`

Output:
- `data/predictions/{model_name}_predictions.parquet`, or variant-specific files such as `data/predictions/ridge_reg_nlp_plus_external_predictions.parquet`
- `outputs/tables/{model_name}/model_metrics.csv`

### 5. `backtest`

This stage reads one or more saved prediction files for the selected model and runs a daily portfolio backtest.

Each prediction opens a fixed-size long or short position at `entry_date` and closes it at `exit_date`. If positions overlap in time, they coexist in the portfolio. Daily strategy return is computed as:

`sum(position * stock_daily_return) / sum(abs(position))`

where each active trade contributes one unit of capital. If there are no active positions on a date, the strategy return is `0`. The benchmark is tracked separately using its own daily return series.

A small example:

```text
2024-01-02: long A opens
2024-01-04: short B opens while A is still active
2024-01-05: portfolio return = (1 * ret_A + (-1) * ret_B) / 2
```

This fixes the main issue in the earlier version, where overlapping 5-day or 21-day event returns were being compounded as if they were sequential and fully self-financing.

Output:
- `outputs/tables/{model_name}/backtest_detail.csv`
- `outputs/tables/{model_name}/backtest_summary.csv`
- `outputs/figures/{model_name}/event_equity_curve.png`

### 6. `report`

This stage scans the predictions directory, loads all available prediction files, compares them side by side, and creates summary CSVs plus comparison plots.

Output:
- `outputs/reports/model_report/model_comparison_summary.csv`
- `outputs/reports/model_report/model_event_backtest_summary.csv`
- `outputs/reports/model_report/*.png`

## Main Configuration

The most important settings in [config/default.yaml](/C:/Users/Lenovo/Desktop/Baruch/MFE/2026Spring/Natural%20Language%20Process/HW1/config/default.yaml:1) are:

- `llm.provider`, `llm.model_name`: which extraction backend to use
- `price.benchmark`: benchmark ticker used for excess-return targets
- `target.window_size`: holding horizon in trading days
- `target.use_excess`: whether to predict benchmark-relative return
- `split.n_train_per_ticker`: time-based train/test split per ticker
- `feature.use_external_signals`: whether to add the external price-volume features and compare `nlp_only` against `nlp_plus_external`
- `model.retain_benchmark_return`: whether benchmark return stays in prediction dataframes for plotting and backtesting
- `backtest.greater_is_better`: whether higher predictions imply stronger long candidates
- `backtest.long_threshold`, `backtest.short_threshold`: trade entry rules
- `backtest.annualization_days`: scaling factor for annualized mean return, volatility, and Sharpe

## Source Modules

This section explains what each file in `src/` does and how it fits into the pipeline.

### src/pipeline.py

This is the orchestrator. It wires together every stage, loads the config, resolves benchmark column names, and writes outputs to the right directories.

Key functions:
- `parse_stage`
- `extract_stage`
- `features_stage`
- `model_stage`
- `backtest_stage`
- `report_stage`
- `run_stage`

If you want to understand the project from top to bottom, this is the best file to start with.

### src/transcript_parser.py

This module turns a raw transcript into structured content. It extracts metadata such as ticker and quarter, splits prepared remarks from Q&A, groups text by speaker, and removes repeated blocks.

The output is the clean transcript object that the extraction prompt consumes.

### src/speaker_labeling.py

This module normalizes speaker identities into finance-relevant roles such as `ceo`, `cfo`, `analyst`, `ir`, and `operator`.

That role normalization matters because the later feature engineering step explicitly uses speaker-level sentiment, including CEO sentiment, CFO sentiment, and analyst tone.

### src/prompts.py

This module constructs the extraction prompt. It merges the transcript content with the system prompt, field definitions, the controlled topic vocabulary, and the few-shot example from `config/prompts.yaml`.

Its job is to keep the extraction format stable enough for downstream parsing.

### src/schemas.py

This module validates and normalizes the LLM output. It fills missing fields, coerces types where possible, and ensures the JSON schema is consistent enough for feature engineering.

Without this layer, one malformed response could easily break the rest of the pipeline.

### src/llm_client.py

This module abstracts the LLM backend. It supports both OpenAI and Ollama, so the rest of the code can request an extraction without worrying about provider-specific API details.

### src/extractor.py

This is the extraction engine. It loads a parsed transcript, sends the prompt through the LLM client, saves the raw response, validates it, and writes the cleaned JSON used later by the feature builder.

In practice, this is the bridge between unstructured text and structured quantitative features.

### src/features.py

This module converts the validated extraction JSON into a feature dataframe. The feature set mixes:

- call-level sentiment and guidance
- speaker-level sentiment dispersion and consistency
- proactive vs reactive topic behavior
- risk persistence and new-risk flags
- quarter-over-quarter feature deltas within ticker
- optional external price-volume features such as 5-day mean return, MACD, and `Volume / ADV20`

This file is where the financial NLP design becomes a machine-learning table.

### src/price_loader.py

This module downloads and caches benchmark and single-name price histories with `yfinance`. It now keeps both `Close` and `Volume`, so the same cache can support target construction, external features, and daily backtesting.

The cached prices are reused in later runs so the pipeline does not need to fetch the same data every time.

### src/target_builder.py

This module aligns features with post-call market outcomes. It computes entry and exit dates, raw forward returns, benchmark returns, benchmark-adjusted returns, and optional classification targets.

Right now the default target is `y_excess`, which is the stock return minus the benchmark return over the chosen holding window.

### src/split.py

This module creates the time-based split. For each ticker, it sorts the calls chronologically and marks the first `n_train_per_ticker` observations as train and the rest as test.

That design avoids leakage from future calls into earlier model fitting.

### src/models.py

This module handles model preparation, fitting, prediction, and basic evaluation.

It currently supports:

- regression: `ridge_reg`, `rf_reg`, `xgb_reg`
- classification: `logistic_clf`, `rf_clf`, `xgb_clf`

It also checks whether the chosen model is compatible with the chosen target type.

### src/backtest.py

This module evaluates prediction usefulness in trading terms. It now builds a daily strategy curve from overlapping fixed-size event positions, aggregates returns across all active trades, and compares that curve with a continuously updated benchmark curve.

It also annualizes summary statistics and uses `greater_is_better` to interpret model scores correctly.

### src/model_report.py

This module builds the multi-model report from saved prediction files. It compares regression quality and daily event backtests, then generates summary plots across all saved predictions.

This is the easiest way to compare several trained models side by side.

### src/utils.py

This module holds project-wide helpers for:

- YAML and JSON I/O
- parquet reads and writes
- logging
- directory creation
- date utilities
- response cleanup

It is shared by nearly every other module.

## Current Default Experiment

With the current configuration, the pipeline does the following:

- parses transcript files from `data/raw/transcripts/`
- extracts one unified JSON per call
- builds a modeling table with benchmark-relative forward returns
- uses the first 6 calls per ticker for training
- trains a selected model on numeric NLP features
- saves predictions into `data/predictions/`
- optionally compares `nlp_only` and `nlp_plus_external`
- runs a daily backtest and optionally compares multiple saved predictions

## Reproducibility Notes

- If you change the prompt or feature definitions, rerun from `--stage extract` or `--stage features` as appropriate.
- If you change the benchmark, any target/y definition, split settings, or external signal setting, rerun from `--stage features`.
- If you change only model hyperparameters, rerun from `--stage model`.
- If multiple prediction files are saved in `data/predictions/`, the `report` stage will include all of them.

## Outputs To Check First

If you want the quickest sense of what happened in a run, open these files first:

- `data/processed/modeling_table.parquet`
- `outputs/tables/{model_name}/model_metrics.csv`
- `outputs/tables/{model_name}/backtest_summary.csv`
- `outputs/reports/model_report/model_comparison_summary.csv`
- `outputs/reports/model_report/model_event_backtest_summary.csv`
