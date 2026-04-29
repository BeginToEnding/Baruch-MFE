import itertools
import json
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from .models import (
    LABEL_TO_INT,
    _concat_enriched_features,
    _load_feature_blocks,
    _split_arrays,
    _y_from_df,
    apply_model_params,
    predict_fasttext_model,
    predict_rules_regex_model,
    train_fasttext_model,
    train_linear_embedding_model,
    train_rules_regex_model,
    train_tree_enriched_model,
)
from .thresholding import search_thresholds
from .utils import output_path, save_json, save_parquet


def _param_combinations(grid: Dict) -> List[Dict]:
    if not grid:
        return [{}]
    keys = list(grid)
    values = [v if isinstance(v, list) else [v] for v in grid.values()]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _score_thresholds(y_true: np.ndarray, proba: np.ndarray, cfg: Dict) -> Dict:
    thresholds = np.linspace(
        float(cfg["training"]["threshold_grid_min"]),
        float(cfg["training"]["threshold_grid_max"]),
        int(cfg["training"]["threshold_grid_points"]),
    )
    detail = search_thresholds(y_true, proba, thresholds, float(cfg["project"]["recall_floor_substantive"]))
    feasible = detail[detail["meets_floor"]].sort_values(["macro_f1", "threshold"], ascending=[False, True])
    if feasible.empty:
        best = detail.sort_values(["substantive_recall", "macro_f1"], ascending=[False, False]).iloc[0]
        feasible_flag = False
    else:
        best = feasible.iloc[0]
        feasible_flag = True
    return {
        "threshold": float(best["threshold"]),
        "substantive_recall": float(best["substantive_recall"]),
        "macro_f1": float(best["macro_f1"]),
        "meets_floor": bool(feasible_flag),
    }


def _predict_candidate(family: str, cfg: Dict, feat_df: pd.DataFrame, emb: np.ndarray, train_idx: np.ndarray, val_idx: np.ndarray, train_df: pd.DataFrame, logger) -> np.ndarray | None:
    if family == "rules_regex":
        model = train_rules_regex_model(feat_df.iloc[train_idx])
        return predict_rules_regex_model(model, feat_df.iloc[val_idx])
    if family == "linear_embeddings":
        model = train_linear_embedding_model(emb[train_idx], train_df["y"].to_numpy(), cfg)
        return model.predict_proba(emb[val_idx])[:, 1]
    if family == "tree_enriched":
        X = _concat_enriched_features(feat_df, emb)
        model = train_tree_enriched_model(X[train_idx], train_df["y"].to_numpy(), cfg)
        return model.predict_proba(X[val_idx])[:, 1]
    if family == "fasttext":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            model = train_fasttext_model(
                train_df,
                cfg,
                logger,
                train_path=tmp_dir / "fasttext_train.txt",
                model_path=tmp_dir / "fasttext.bin",
            )
            if model is None:
                return None
            return predict_fasttext_model(tmp_dir / "fasttext.bin", feat_df.iloc[val_idx]["sentence_text"].tolist())
    logger.warning("Skipping grid search for unsupported family: %s", family)
    return None


def run_hyperparameter_search(cfg: Dict, logger) -> pd.DataFrame:
    feat_df, emb = _load_feature_blocks(cfg)
    train_idx, val_idx, _ = _split_arrays(feat_df, emb)
    train_df = feat_df.iloc[train_idx].copy()
    val_df = feat_df.iloc[val_idx].copy()
    train_df["y"] = _y_from_df(train_df)
    y_val = val_df["label"].map(LABEL_TO_INT).to_numpy()

    search_cfg = cfg.get("hyperparameter_search", {})
    families = search_cfg.get("include_families", [])
    grids = search_cfg.get("grids", {})
    max_combos = int(search_cfg.get("max_combinations_per_family", 81))
    
    rows = []
    best = {}
    for family in families:
        if family not in cfg["training"]["benchmark_families"]:
            logger.info("Skipping %s because it is not in training.benchmark_families", family)
            continue
        combos = _param_combinations(grids.get(family, {}))
        if len(combos) > max_combos:
            raise ValueError(f"{family} grid has {len(combos)} combinations, above max {max_combos}")
        logger.info("Grid searching %s over %d combinations", family, len(combos))
        for combo_i, params in enumerate(combos):
            candidate_cfg = apply_model_params(cfg, family, params)
            t0 = time.perf_counter()
            proba = _predict_candidate(family, candidate_cfg, feat_df, emb, train_idx, val_idx, train_df, logger)
            train_score_sec = time.perf_counter() - t0
            if proba is None:
                continue
            score = _score_thresholds(y_val, proba, cfg)
            row = {
                "family": family,
                "combo_i": combo_i,
                "params": params,
                "params_json": json.dumps(params, sort_keys=True),
                "train_score_seconds": train_score_sec,
                **score,
            }
            rows.append(row)

        family_rows = [r for r in rows if r["family"] == family]
        feasible = [r for r in family_rows if r["meets_floor"]]
        candidates = feasible if feasible else family_rows
        if candidates:
            chosen = sorted(candidates, key=lambda r: (r["macro_f1"], r["substantive_recall"], -r["threshold"]), reverse=True)[0]
            best[family] = {
                "params": chosen["params"],
                "threshold": chosen["threshold"],
                "macro_f1": chosen["macro_f1"],
                "substantive_recall": chosen["substantive_recall"],
                "meets_floor": chosen["meets_floor"],
            }

    result = pd.DataFrame(rows)
    if "params" in result.columns:
        result = result.drop(columns=["params"])
    save_parquet(result, output_path(cfg, "grid_search", "grid_search_results.parquet"))
    save_json(best, output_path(cfg, "grid_search", "best_hyperparams.json"))
    save_json({k: {"threshold_mean": v["threshold"], "recall_floor": float(cfg["project"]["recall_floor_substantive"])} for k, v in best.items()}, output_path(cfg, "grid_search", "grid_search_best_thresholds.json"))
    logger.info("Saved grid search results for %d families", len(best))
    return result
