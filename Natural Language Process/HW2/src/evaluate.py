import time
from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

from .models import INT_TO_LABEL, LABEL_TO_INT, predict_family_proba
from .utils import artifact_path, cache_path, interim_path, load_json, output_path, read_parquet, save_json, save_parquet


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, labels=[1, 0], zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "boilerplate_precision": float(p[0]),
        "boilerplate_recall": float(r[0]),
        "boilerplate_f1": float(f[0]),
        "substantive_precision": float(p[1]),
        "substantive_recall": float(r[1]),
        "substantive_f1": float(f[1]),
    }


def _plot_confusion_matrix(cm: np.ndarray, save_path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.imshow(cm)
    ax.set_xticks([0, 1], ["boilerplate", "substantive"])
    ax.set_yticks([0, 1], ["boilerplate", "substantive"])
    ax.set_title(title)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, int(cm[i, j]), ha="center", va="center")
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=160)
    plt.close(fig)


def _export_references(cfg: Dict) -> None:
    refs = {
        "libraries": ["scikit-learn", "sentence-transformers", "transformers", "setfit", "streamlit", "nltk", "openai", "anthropic", "requests", "pyarrow"],
        "pretrained_models": {
            "sentence_embedding_model": cfg["features"]["sentence_embedding_model"],
            "finbert": cfg["models"]["finbert"]["pretrained_name"],
            "setfit": cfg["models"]["setfit"]["pretrained_name"],
            "ollama_judge": [j["model"] for j in cfg["labeling"]["judges"] if j["provider"] == "ollama"],
        },
        "apis": [j["provider"] for j in cfg["labeling"]["judges"] if j.get("enabled", True)],
    }
    save_json(refs, output_path(cfg, "evaluation", "references_export.json"))


def _weighted_average_probabilities(proba_store: Dict[str, np.ndarray], weights: Dict[str, float], members: list[str]) -> np.ndarray:
    raw_weights = np.asarray([max(float(weights.get(member, 0.0)), 0.0) for member in members], dtype=float)
    if raw_weights.sum() <= 0:
        raw_weights = np.ones(len(members), dtype=float)
    normalized = raw_weights / raw_weights.sum()
    stacked = np.vstack([proba_store[member] for member in members])
    return np.average(stacked, axis=0, weights=normalized)


def evaluate_all_models(cfg: Dict, logger) -> pd.DataFrame:
    feat_df = read_parquet(interim_path(cfg, "features_regex.parquet"))
    emb = np.load(cache_path(cfg, "embeddings_all.npy"))
    manifest = load_json(artifact_path(cfg, "models", "manifest.json"))
    thresholds = load_json(output_path(cfg, "thresholds", "best_thresholds.json"))

    test_df = feat_df[feat_df["split"] == "test"].copy()
    test_idx = test_df.index.to_numpy()
    y_true = test_df["label"].map(LABEL_TO_INT).to_numpy()

    rows, proba_store, family_notes = [], {}, {}
    for item in manifest:
        family = item["family"]
        t0 = time.perf_counter()
        proba = predict_family_proba(cfg, family, feat_df.iloc[test_idx], emb[test_idx], texts=test_df["sentence_text"].tolist())
        elapsed = time.perf_counter() - t0
        threshold = thresholds.get(family, {}).get("threshold", thresholds.get(family, {}).get("threshold_mean", 0.5))
        pred = (proba >= threshold).astype(int)
        metrics = _compute_metrics(y_true, pred)
        metrics.update({"family": family, "threshold": float(threshold), "inference_sent_per_sec": float(len(test_df) / max(elapsed, 1e-9)), "recall_floor_pass": metrics["substantive_recall"] >= float(cfg["project"]["recall_floor_substantive"])})
        rows.append(metrics)
        proba_store[family] = proba

        cm = confusion_matrix(y_true, pred, labels=[1, 0])
        _plot_confusion_matrix(cm, artifact_path(cfg, "figures", f"cm_{family}.png"), f"Confusion Matrix: {family}")
        
        fam_df = test_df[["sentence_id", "sentence_text", "label"]].copy()
        fam_df["pred_label"] = [INT_TO_LABEL[int(v)] for v in pred]
        fam_df["boilerplate_proba"] = proba
        fam_df["is_error"] = fam_df["label"] != fam_df["pred_label"]
        fam_df.to_csv(output_path(cfg, "error_analysis", f"error_analysis_{family}.csv"), index=False)
        errors = fam_df[fam_df["is_error"]]
        family_notes[family] = {"n_test": int(len(fam_df)), "n_errors": int(len(errors)), "likely_strength": "High boilerplate precision on stereotyped patterns" if family == "rules_regex" else "Captures broader semantic context", "likely_failure_mode": "Mixed or ambiguous sentences" if len(errors) else "Few visible failures on current test split", "example_error_sentence": None if errors.empty else errors.iloc[0]["sentence_text"]}
    
    if len(proba_store) >= 2 and "ensemble" in cfg["training"]["benchmark_families"]:
        ensemble_path = artifact_path(cfg, "models", "ensemble.json")
        if ensemble_path.exists():
            ensemble_cfg = load_json(ensemble_path)
            topk = [family for family in ensemble_cfg["topk_members"] if family in proba_store]
        else:
            ensemble_cfg = {}
            topk = []
        if topk:
            weights = {family: float(ensemble_cfg.get("weights", {}).get(family, 1.0)) for family in topk}
            proba = _weighted_average_probabilities(proba_store, weights, topk)
            threshold = float(thresholds.get("ensemble", {}).get("threshold", ensemble_cfg.get("threshold", 0.5)))
            pred = (proba >= threshold).astype(int)
            metrics = _compute_metrics(y_true, pred)
            metrics.update({"family": "ensemble", "threshold": threshold, "inference_sent_per_sec": None, "recall_floor_pass": metrics["substantive_recall"] >= float(cfg["project"]["recall_floor_substantive"])})
            rows.append(metrics)
            cm = confusion_matrix(y_true, pred, labels=[1, 0])
            _plot_confusion_matrix(cm, artifact_path(cfg, "figures", "cm_ensemble.png"), "Confusion Matrix: ensemble")
            fam_df = test_df[["sentence_id", "sentence_text", "label"]].copy()
            fam_df["pred_label"] = [INT_TO_LABEL[int(v)] for v in pred]
            fam_df["boilerplate_proba"] = proba
            fam_df["is_error"] = fam_df["label"] != fam_df["pred_label"]
            fam_df.to_csv(output_path(cfg, "error_analysis", "error_analysis_ensemble.csv"), index=False)
            errors = fam_df[fam_df["is_error"]]
            family_notes["ensemble"] = {
                "n_test": int(len(test_df)),
                "n_errors": int(len(errors)),
                "likely_strength": "OOF-weighted probability average of non-transformer members",
                "likely_failure_mode": "Can average away strong single-model signals",
                "example_error_sentence": None if errors.empty else errors.iloc[0]["sentence_text"],
                "topk_members": topk,
                "weights": weights,
            }

    leaderboard = pd.DataFrame(rows).sort_values(["macro_f1", "substantive_recall"], ascending=[False, False]).reset_index(drop=True)
    save_parquet(leaderboard, output_path(cfg, "evaluation", "leaderboard.parquet"))
    leaderboard.to_csv(output_path(cfg, "evaluation", "leaderboard.csv"), index=False)
    best = leaderboard.iloc[0].to_dict()
    save_json(best, output_path(cfg, "evaluation", "best_model_selection.json"))
    save_json(family_notes, output_path(cfg, "evaluation", "family_writeup_notes.json"))

    best_family, threshold = best["family"], float(best["threshold"])
    if best_family == "ensemble":
        ensemble_cfg = load_json(artifact_path(cfg, "models", "ensemble.json"))
        topk = [family for family in ensemble_cfg["topk_members"] if family in proba_store]
        weights = {family: float(ensemble_cfg.get("weights", {}).get(family, 1.0)) for family in topk}
        best_proba = _weighted_average_probabilities(proba_store, weights, topk)
    else:
        best_proba = proba_store[best_family]
    best_pred = (best_proba >= threshold).astype(int)
    error_df = test_df[["sentence_id", "sentence_text", "label"]].copy()
    error_df["pred_label"] = [INT_TO_LABEL[int(v)] for v in best_pred]
    error_df["boilerplate_proba"] = best_proba
    error_df["is_error"] = error_df["label"] != error_df["pred_label"]
    save_parquet(error_df, output_path(cfg, "error_analysis", "error_analysis.parquet"))
    error_df.to_csv(output_path(cfg, "error_analysis", "error_analysis.csv"), index=False)
    _export_references(cfg)
    logger.info("Saved leaderboard, per-family errors, notes, and references export")
    return leaderboard


def package_best_model(cfg: Dict, logger) -> None:
    best = load_json(output_path(cfg, "evaluation", "best_model_selection.json"))
    package = {"family": best["family"], "threshold": float(best["threshold"])}
    if best["family"] == "ensemble":
        package["ensemble"] = load_json(artifact_path(cfg, "models", "ensemble.json"))
    save_json(package, artifact_path(cfg, "best_model", "metadata.json"))
    logger.info("Packaged best model metadata for %s", best["family"])
