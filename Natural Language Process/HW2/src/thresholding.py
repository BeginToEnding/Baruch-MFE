import tempfile
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, recall_score
from sklearn.model_selection import StratifiedKFold

from .models import (
    LABEL_TO_INT,
    _concat_enriched_features,
    _predict_proba_finbert,
    _predict_proba_setfit,
    _train_finbert,
    _train_setfit,
    apply_model_params,
    cfg_with_best_hyperparams,
    predict_fasttext_model,
    predict_rules_regex_model,
    train_fasttext_model,
    train_linear_embedding_model,
    train_rules_regex_model,
    train_tree_enriched_model,
)
from .utils import artifact_path, cache_path, interim_path, load_json, output_path, read_parquet, save_json, save_parquet


def make_threshold_grid(cfg: Dict) -> np.ndarray:
    return np.linspace(
        float(cfg["training"]["threshold_grid_min"]),
        float(cfg["training"]["threshold_grid_max"]),
        int(cfg["training"]["threshold_grid_points"]),
    )


def search_thresholds(y_true: np.ndarray, proba: np.ndarray, thresholds: np.ndarray, recall_floor: float) -> pd.DataFrame:
    proba = np.clip(np.asarray(proba, dtype=float), 0.0, 1.0)
    if len(proba):
        proba_min = float(np.min(proba))
        proba_max = float(np.max(proba))
        thresholds = np.asarray([t for t in thresholds if proba_min <= t <= proba_max], dtype=float)
        thresholds = np.unique(np.concatenate([thresholds, np.array([proba_min, proba_max], dtype=float)]))
    rows = []
    for t in thresholds:
        pred = (proba >= t).astype(int)
        substantive_recall = recall_score(
            (y_true == LABEL_TO_INT["substantive"]).astype(int),
            (pred == LABEL_TO_INT["substantive"]).astype(int),
            zero_division=0,
        )
        macro_f1 = f1_score(y_true, pred, average="macro", zero_division=0)
        rows.append({
            "threshold": float(t),
            "substantive_recall": substantive_recall,
            "macro_f1": macro_f1,
            "meets_floor": substantive_recall >= recall_floor,
        })
    return pd.DataFrame(rows)


def select_best_threshold(threshold_df: pd.DataFrame) -> pd.Series:
    feasible = threshold_df[threshold_df["meets_floor"]].sort_values(["macro_f1", "threshold"], ascending=[False, True])
    if len(feasible):
        return feasible.iloc[0]
    return threshold_df.sort_values(["substantive_recall", "macro_f1"], ascending=[False, False]).iloc[0]


def _weighted_average_probabilities(proba_by_family: Dict[str, np.ndarray], weights: Dict[str, float], members: list[str]) -> np.ndarray:
    raw_weights = np.asarray([max(float(weights.get(member, 0.0)), 0.0) for member in members], dtype=float)
    if raw_weights.sum() <= 0:
        raw_weights = np.ones(len(members), dtype=float)
    normalized = raw_weights / raw_weights.sum()
    stacked = np.vstack([proba_by_family[member] for member in members])
    return np.average(stacked, axis=0, weights=normalized)


def _ensemble_include_transformers(cfg: Dict) -> bool:
    return bool(cfg.get("models", {}).get("ensemble", {}).get("include_transformers", False))


def _ensemble_candidate_families(cfg: Dict, families: list[str]) -> list[str]:
    blocked = {"ensemble"}
    if not _ensemble_include_transformers(cfg):
        blocked.update({"finbert", "setfit"})
    return [family for family in families if family not in blocked]


def _train_predict_fold(cfg: Dict, family: str, feat_df: pd.DataFrame, emb: np.ndarray, train_idx: np.ndarray, holdout_idx: np.ndarray, logger) -> np.ndarray:
    train_df = feat_df.iloc[train_idx].copy()
    holdout_df = feat_df.iloc[holdout_idx].copy()
    train_df["y"] = train_df["label"].map(LABEL_TO_INT).to_numpy()

    if family == "rules_regex":
        model = train_rules_regex_model(train_df)
        return predict_rules_regex_model(model, holdout_df)

    if family == "linear_embeddings":
        model = train_linear_embedding_model(emb[train_idx], train_df["y"].to_numpy(), cfg)
        return model.predict_proba(emb[holdout_idx])[:, 1]

    if family == "tree_enriched":
        X = _concat_enriched_features(feat_df, emb)
        model = train_tree_enriched_model(X[train_idx], train_df["y"].to_numpy(), cfg)
        return model.predict_proba(X[holdout_idx])[:, 1]

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
                raise RuntimeError("fastText dependencies unavailable")
            return predict_fasttext_model(tmp_dir / "fasttext.bin", holdout_df["sentence_text"].tolist())

    if family == "finbert":
        val_df = holdout_df.copy()
        val_df["y"] = val_df["label"].map(LABEL_TO_INT).to_numpy()
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "finbert"
            model = _train_finbert(train_df, val_df, cfg, logger, out_dir=out_dir)
            if model is None:
                raise RuntimeError("FinBERT dependencies unavailable")
            return _predict_proba_finbert(out_dir, holdout_df["sentence_text"].tolist())

    if family == "setfit":
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "setfit"
            model = _train_setfit(train_df, cfg, logger, out_dir=out_dir)
            if model is None:
                raise RuntimeError("SetFit dependencies unavailable")
            return _predict_proba_setfit(out_dir, holdout_df["sentence_text"].tolist())

    raise ValueError(f"Unsupported family for OOF thresholding: {family}")


def build_oof_probabilities(cfg: Dict, family: str, feat_df: pd.DataFrame, trainval: pd.DataFrame, trainval_idx: np.ndarray, emb: np.ndarray, y: np.ndarray, logger) -> tuple[np.ndarray, list[float], list[pd.DataFrame]]:
    skf = StratifiedKFold(
        n_splits=int(cfg["training"]["cv_folds"]),
        shuffle=True,
        random_state=int(cfg["project"]["random_seed"]),
    )
    thresholds = make_threshold_grid(cfg)
    recall_floor = float(cfg["project"]["recall_floor_substantive"])

    oof_proba = np.zeros(len(trainval), dtype=float)
    fold_best = []
    fold_details = []
    for fold_i, (fit_pos, holdout_pos) in enumerate(skf.split(np.zeros(len(y)), y)):
        logger.info("OOF thresholding %s fold %d/%d", family, fold_i + 1, int(cfg["training"]["cv_folds"]))
        fit_idx = trainval_idx[fit_pos]
        holdout_idx = trainval_idx[holdout_pos]
        proba = _train_predict_fold(cfg, family, feat_df, emb, fit_idx, holdout_idx, logger)
        proba = np.clip(np.asarray(proba, dtype=float), 0.0, 1.0)
        oof_proba[holdout_pos] = proba

        fold_df = search_thresholds(y[holdout_pos], proba, thresholds, recall_floor)
        fold_best_row = select_best_threshold(fold_df)
        fold_best.append(float(fold_best_row["threshold"]))
        fold_df["family"] = family
        fold_df["fold"] = fold_i
        fold_details.append(fold_df)

    return oof_proba, fold_best, fold_details


def _load_threshold_artifacts(cfg: Dict) -> tuple[pd.DataFrame, pd.DataFrame, Dict]:
    detail_path = output_path(cfg, "thresholds", "threshold_search.parquet")
    oof_path = output_path(cfg, "thresholds", "oof_probabilities.parquet")
    best_path = output_path(cfg, "thresholds", "best_thresholds.json")
    detail = read_parquet(detail_path) if detail_path.exists() else pd.DataFrame()
    oof_predictions = read_parquet(oof_path) if oof_path.exists() else pd.DataFrame()
    best = load_json(best_path) if best_path.exists() else {}
    return detail, oof_predictions, best


def _save_threshold_artifacts(cfg: Dict, detail: pd.DataFrame, oof_predictions: pd.DataFrame, best: Dict) -> None:
    save_parquet(detail, output_path(cfg, "thresholds", "threshold_search.parquet"))
    save_parquet(oof_predictions, output_path(cfg, "thresholds", "oof_probabilities.parquet"))
    save_json(best, output_path(cfg, "thresholds", "best_thresholds.json"))


def _replace_family_rows(df: pd.DataFrame, family: str, replacement: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "family" not in df.columns:
        return replacement.reset_index(drop=True)
    kept = df[df["family"] != family].copy()
    return pd.concat([kept, replacement], ignore_index=True)


def _family_oof_frame(trainval: pd.DataFrame, family: str, oof_proba: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({
        "family": family,
        "sentence_id": trainval["sentence_id"].to_numpy(),
        "label": trainval["label"].to_numpy(),
        "boilerplate_proba_oof": oof_proba,
    })


def _tune_one_family_threshold(cfg: Dict, family: str, feat_df: pd.DataFrame, trainval: pd.DataFrame, trainval_idx: np.ndarray, emb: np.ndarray, y: np.ndarray, logger) -> None:
    recall_floor = float(cfg["project"]["recall_floor_substantive"])
    thresholds = make_threshold_grid(cfg)
    detail, oof_predictions, best = _load_threshold_artifacts(cfg)

    logger.info("Building 5-fold OOF probabilities for %s", family)
    oof_proba, fold_best, fold_details = build_oof_probabilities(cfg, family, feat_df, trainval, trainval_idx, emb, y, logger)
    pooled_df = search_thresholds(y, oof_proba, thresholds, recall_floor)
    pooled_best = select_best_threshold(pooled_df)
    pooled_df["family"] = family
    pooled_df["fold"] = -1
    pooled_df["fold_name"] = "pooled_oof"

    family_detail = pd.concat(fold_details + [pooled_df], ignore_index=True)
    best[family] = {
        "threshold": float(pooled_best["threshold"]),
        "threshold_mean": float(np.mean(fold_best)),
        "threshold_std": float(np.std(fold_best)),
        "fold_thresholds": fold_best,
        "pooled_oof_macro_f1": float(pooled_best["macro_f1"]),
        "pooled_oof_substantive_recall": float(pooled_best["substantive_recall"]),
        "pooled_oof_meets_floor": bool(pooled_best["meets_floor"]),
        "recall_floor": recall_floor,
    }

    detail = _replace_family_rows(detail, family, family_detail)
    oof_predictions = _replace_family_rows(oof_predictions, family, _family_oof_frame(trainval, family, oof_proba))
    _save_threshold_artifacts(cfg, detail, oof_predictions, best)
    logger.info("Saved threshold outputs for %s", family)


def _oof_arrays_from_saved(trainval: pd.DataFrame, oof_predictions: pd.DataFrame, families: list[str]) -> Dict[str, np.ndarray]:
    arrays = {}
    order = trainval[["sentence_id"]].copy()
    for family in families:
        fam = oof_predictions[oof_predictions["family"] == family][["sentence_id", "boilerplate_proba_oof"]].copy()
        merged = order.merge(fam, on="sentence_id", how="left")
        if merged["boilerplate_proba_oof"].isna().any():
            continue
        arrays[family] = merged["boilerplate_proba_oof"].to_numpy(dtype=float)
    return arrays


def _tune_ensemble_from_saved_oof(cfg: Dict, trainval: pd.DataFrame, y: np.ndarray, logger) -> None:
    recall_floor = float(cfg["project"]["recall_floor_substantive"])
    thresholds = make_threshold_grid(cfg)
    detail, oof_predictions, best = _load_threshold_artifacts(cfg)
    if oof_predictions.empty:
        raise ValueError("Cannot tune ensemble: outputs/oof_probabilities.parquet does not exist or is empty. Tune member models first.")

    saved_families = _ensemble_candidate_families(cfg, oof_predictions["family"].dropna().unique().tolist())
    candidate_families = [
        family
        for family in saved_families
        if family in best and "pooled_oof_macro_f1" in best[family]
    ]
    candidate_families = sorted(candidate_families, key=lambda f: float(best[f]["pooled_oof_macro_f1"]), reverse=True)
    topk = candidate_families[: int(cfg["project"]["top_k_for_ensemble"])]
    if len(topk) < 2:
        raise ValueError(f"Cannot tune ensemble: need at least 2 saved OOF members, found {topk}")

    oof_by_family = _oof_arrays_from_saved(trainval, oof_predictions, topk)
    topk = [family for family in topk if family in oof_by_family]
    if len(topk) < 2:
        raise ValueError(f"Cannot tune ensemble: saved OOF rows are incomplete for selected members, found {topk}")

    weights = {family: float(best[family]["pooled_oof_macro_f1"]) for family in topk}
    ensemble_oof_proba = _weighted_average_probabilities(oof_by_family, weights, topk)
    ensemble_df = search_thresholds(y, ensemble_oof_proba, thresholds, recall_floor)
    ensemble_best = select_best_threshold(ensemble_df)
    ensemble_df["family"] = "ensemble"
    ensemble_df["fold"] = -1
    ensemble_df["fold_name"] = "pooled_oof_weighted"
    
    best["ensemble"] = {
        "threshold": float(ensemble_best["threshold"]),
        "pooled_oof_macro_f1": float(ensemble_best["macro_f1"]),
        "pooled_oof_substantive_recall": float(ensemble_best["substantive_recall"]),
        "pooled_oof_meets_floor": bool(ensemble_best["meets_floor"]),
        "recall_floor": recall_floor,
        "method": "weighted_probability",
        "weight_metric": "pooled_oof_macro_f1",
        "include_transformers": _ensemble_include_transformers(cfg),
        "topk_members": topk,
        "weights": weights,
    }
    detail = _replace_family_rows(detail, "ensemble", ensemble_df)
    oof_predictions = _replace_family_rows(oof_predictions, "ensemble", _family_oof_frame(trainval, "ensemble", ensemble_oof_proba))
    save_json(
        {
            "method": "weighted_probability",
            "weight_metric": "pooled_oof_macro_f1",
            "include_transformers": _ensemble_include_transformers(cfg),
            "topk_members": topk,
            "weights": weights,
            "threshold": float(ensemble_best["threshold"]),
        },
        artifact_path(cfg, "models", "ensemble.json"),
    )
    _save_threshold_artifacts(cfg, detail, oof_predictions, best)
    logger.info("Saved weighted probability ensemble threshold using members: %s", ", ".join(topk))


def tune_all_thresholds(cfg: Dict, logger, family: str | None = None) -> None:
    cfg = cfg_with_best_hyperparams(cfg, logger)
    feat_df = read_parquet(interim_path(cfg, "features_regex.parquet"))
    emb = np.load(cache_path(cfg, "embeddings_all.npy"))
    manifest = load_json(artifact_path(cfg, "models", "manifest.json"))

    trainval = feat_df[feat_df["split"].isin(["train", "val"])].copy()
    trainval_idx = trainval.index.to_numpy()
    y = trainval["label"].map(LABEL_TO_INT).to_numpy()

    if family:
        if family == "ensemble":
            _tune_ensemble_from_saved_oof(cfg, trainval, y, logger)
            return
        manifest_families = {item["family"] for item in manifest}
        if family not in manifest_families:
            raise ValueError(f"Cannot tune {family}: not found in artifacts/models/manifest.json")
        _tune_one_family_threshold(cfg, family, feat_df, trainval, trainval_idx, emb, y, logger)
        return

    recall_floor = float(cfg["project"]["recall_floor_substantive"])
    thresholds = make_threshold_grid(cfg)

    all_rows = []
    best = {}
    oof_rows = []
    oof_by_family = {}
    
    def _checkpoint() -> None:
        detail = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
        oof_predictions = pd.concat(oof_rows, ignore_index=True) if oof_rows else pd.DataFrame()
        save_parquet(detail, output_path(cfg, "thresholds", "threshold_search.parquet"))
        save_parquet(oof_predictions, output_path(cfg, "thresholds", "oof_probabilities.parquet"))
        save_json(best, output_path(cfg, "thresholds", "best_thresholds.json"))

    for item in manifest:
        family = item["family"]
        logger.info("Building 5-fold OOF probabilities for %s", family)
        oof_proba, fold_best, fold_details = build_oof_probabilities(cfg, family, feat_df, trainval, trainval_idx, emb, y, logger)
        all_rows.extend(fold_details)

        pooled_df = search_thresholds(y, oof_proba, thresholds, recall_floor)
        pooled_best = select_best_threshold(pooled_df)
        pooled_df["family"] = family
        pooled_df["fold"] = -1
        pooled_df["fold_name"] = "pooled_oof"
        all_rows.append(pooled_df)

        best[family] = {
            "threshold": float(pooled_best["threshold"]),
            "threshold_mean": float(np.mean(fold_best)),
            "threshold_std": float(np.std(fold_best)),
            "fold_thresholds": fold_best,
            "pooled_oof_macro_f1": float(pooled_best["macro_f1"]),
            "pooled_oof_substantive_recall": float(pooled_best["substantive_recall"]),
            "pooled_oof_meets_floor": bool(pooled_best["meets_floor"]),
            "recall_floor": recall_floor,
        }
        oof_rows.append(pd.DataFrame({
            "family": family,
            "sentence_id": trainval["sentence_id"].to_numpy(),
            "label": trainval["label"].to_numpy(),
            "boilerplate_proba_oof": oof_proba,
        }))
        oof_by_family[family] = oof_proba
        _checkpoint()
        logger.info("Checkpointed OOF threshold outputs after %s", family)

    if "ensemble" in cfg["training"]["benchmark_families"]:
        candidate_families = [
            family
            for family, item in sorted(best.items(), key=lambda kv: kv[1]["pooled_oof_macro_f1"], reverse=True)
            if family in _ensemble_candidate_families(cfg, list(oof_by_family))
        ]
        topk = candidate_families[: int(cfg["project"]["top_k_for_ensemble"])]
        if len(topk) >= 2:
            weights = {family: float(best[family]["pooled_oof_macro_f1"]) for family in topk}
            ensemble_oof_proba = _weighted_average_probabilities(oof_by_family, weights, topk)
            ensemble_df = search_thresholds(y, ensemble_oof_proba, thresholds, recall_floor)
            ensemble_best = select_best_threshold(ensemble_df)
            ensemble_df["family"] = "ensemble"
            ensemble_df["fold"] = -1
            ensemble_df["fold_name"] = "pooled_oof_weighted"
            all_rows.append(ensemble_df)
            best["ensemble"] = {
                "threshold": float(ensemble_best["threshold"]),
                "pooled_oof_macro_f1": float(ensemble_best["macro_f1"]),
                "pooled_oof_substantive_recall": float(ensemble_best["substantive_recall"]),
                "pooled_oof_meets_floor": bool(ensemble_best["meets_floor"]),
                "recall_floor": recall_floor,
                "method": "weighted_probability",
                "weight_metric": "pooled_oof_macro_f1",
                "include_transformers": _ensemble_include_transformers(cfg),
                "topk_members": topk,
                "weights": weights,
            }
            oof_rows.append(pd.DataFrame({
                "family": "ensemble",
                "sentence_id": trainval["sentence_id"].to_numpy(),
                "label": trainval["label"].to_numpy(),
                "boilerplate_proba_oof": ensemble_oof_proba,
            }))
            save_json(
                {
                    "method": "weighted_probability",
                    "weight_metric": "pooled_oof_macro_f1",
                    "include_transformers": _ensemble_include_transformers(cfg),
                    "topk_members": topk,
                    "weights": weights,
                    "threshold": float(ensemble_best["threshold"]),
                },
                artifact_path(cfg, "models", "ensemble.json"),
            )
            _checkpoint()
            logger.info("Checkpointed weighted probability ensemble threshold using members: %s", ", ".join(topk))
    logger.info("Saved OOF threshold search outputs")
