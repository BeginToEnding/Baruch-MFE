import copy
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from .utils import artifact_path, cache_path, interim_path, load_json, load_pickle, output_path, read_parquet, save_json, save_pickle

LABEL_TO_INT = {"boilerplate": 1, "substantive": 0}
INT_TO_LABEL = {1: "boilerplate", 0: "substantive"}


RULE_KEYWORDS = {
    "boilerplate": {
        "operator_flow": {
            "keywords": [
                "operator",
                "next question",
                "question comes from",
                "take our next question",
                "our next question is from",
                "conference call",
                "welcome to",
                "good morning",
                "good afternoon",
                "good evening",
            ],
            "weight": 1.2,
        },
        "safe_harbor": {
            "keywords": [
                "forward-looking statement",
                "safe harbor",
                "actual results may differ",
                "risk factors",
                "sec filings",
                "10-k",
                "10-q",
                "8-k",
            ],
            "weight": 1.5,
        },
        "materials_replay": {
            "keywords": [
                "webcast",
                "replay",
                "recording",
                "press release",
                "earnings release",
                "investor relations website",
                "supplemental materials",
                "slide",
            ],
            "weight": 1.0,
        },
        "generic_politeness": {
            "keywords": [
                "thank you for joining",
                "thanks for joining",
                "thank you everyone",
                "turn it over",
                "hand it over",
                "pass it over",
            ],
            "weight": 0.9,
        },
        "speaker_intro": {
            "keywords": [
                "analysts -",
                "executives -",
                "research analyst",
                "joining me today",
                "with me today",
            ],
            "weight": 1.1,
        },
    },
    "substantive": {
        "financial_results": {
            "keywords": [
                "revenue",
                "sales",
                "earnings",
                "eps",
                "margin",
                "gross margin",
                "operating margin",
                "cash flow",
                "free cash flow",
                "balance sheet",
                "capital allocation",
                "buybacks",
                "dividend",
            ],
            "weight": 1.3,
        },
        "guidance_outlook": {
            "keywords": [
                "guidance",
                "outlook",
                "forecast",
                "we expect",
                "we plan",
                "we intend",
                "we are committed",
                "we remain confident",
                "we will continue",
            ],
            "weight": 1.2,
        },
        "business_drivers": {
            "keywords": [
                "demand",
                "pricing",
                "pipeline",
                "backlog",
                "orders",
                "bookings",
                "customers",
                "clients",
                "product",
                "platform",
                "market share",
                "supply chain",
                "inventory",
                "capacity",
                "utilization",
            ],
            "weight": 1.2,
        },
        "strategy_operations": {
            "keywords": [
                "strategy",
                "strategic",
                "priorities",
                "initiative",
                "roadmap",
                "launched",
                "delivered",
                "expanded",
                "invested",
                "acquired",
                "reduced",
                "improved",
                "achieved",
            ],
            "weight": 1.1,
        },
        "contextual_view": {
            "keywords": [
                "we believe",
                "we think",
                "we learned",
                "we could have",
                "because",
                "due to",
                "as a result",
                "driven by",
                "reflecting",
                "tailwind",
                "headwind",
                "those things",
                "that will",
                "this will",
            ],
            "weight": 1.0,
        },
    },
}


RULE_PATTERNS = {
    "boilerplate": {
        "operator_intro": {
            "patterns": [
                r"^(good morning|good afternoon|good evening)\b.*\b(welcome|call)\b",
                r"\b(next question|question comes from|take our next question|next caller)\b",
                r"^\[?operator instructions\]?",
            ],
            "weight": 1.4,
        },
        "legal_disclaimer": {
            "patterns": [
                r"\bforward[- ]looking statements?\b",
                r"\bsafe harbor\b",
                r"\bactual results may differ\b",
                r"\bnon[- ]gaap\b.*\b(gaap|reconciliation|measure)\b",
            ],
            "weight": 1.6,
        },
        "speaker_or_materials": {
            "patterns": [
                r"^(analysts|executives)\s+-\s+",
                r"\b(slide|appendix|supplemental materials?)\s+\d*\b",
                r"\b(webcast|replay|recording)\b",
            ],
            "weight": 1.1,
        },
    },
    "substantive": {
        "financial_metrics": {
            "patterns": [
                r"\$[\d,.]+",
                r"\b\d+(?:\.\d+)?\s*(?:%|percent|basis points?|bps)\b",
                r"\b(revenue|sales|eps|earnings|margin|cash flow)\b.*\b(grew|declined|increased|decreased|improved|expanded|contracted)\b",
                r"\b(q[1-4]|quarter|year[- ]over[- ]year|sequential(?:ly)?)\b.*\b(revenue|sales|margin|eps|earnings)\b",
            ],
            "weight": 1.5,
        },
        "business_question": {
            "patterns": [
                r"\b(can|could|would)\s+you\b.*\b(demand|pricing|margin|revenue|guidance|customer|product|strategy|capital|market)\b",
                r"\b(how|what|why|when|where)\b.*\b(demand|pricing|margin|revenue|guidance|customer|product|strategy|capital|market)\b",
            ],
            "weight": 1.3,
        },
        "business_transition": {
            "patterns": [
                r"\b(turning|moving|now)\s+(to|on)\b.*\b(revenue|margin|guidance|outlook|capital allocation|cash flow|segment|business|strategy|nii|expenses)\b",
                r"\b(discuss|review|cover)\b.*\b(performance|results|guidance|outlook|strategy|capital allocation|business)\b",
            ],
            "weight": 1.1,
        },
        "plans_and_views": {
            "patterns": [
                r"\b(we believe|we think|we expect|we plan|we intend|we are committed|we remain confident)\b",
                r"\b(we learned|we could have|we should have|we will continue|we are going to)\b.*\b(invest|improve|execute|grow|serve|deliver|launch|expand)\b",
                r"\b(it|this|that|they|them|those things)\b.*\b(tailwind|headwind|improve|drive|support|pressure|impact|benefit)\b",
            ],
            "weight": 1.1,
        },
    },
}


def _load_feature_blocks(cfg: Dict) -> Tuple[pd.DataFrame, np.ndarray]:
    feat_df = read_parquet(interim_path(cfg, "features_regex.parquet"))
    emb = np.load(cache_path(cfg, "embeddings_all.npy"))
    return feat_df, emb


def _split_arrays(feat_df: pd.DataFrame, emb: np.ndarray):
    return (feat_df[feat_df["split"] == s].index.to_numpy() for s in ["train", "val", "test"])


def _y_from_df(df: pd.DataFrame) -> np.ndarray:
    return df["label"].map(LABEL_TO_INT).to_numpy()


def _keyword_score(text_lower: str, rule_groups: Dict) -> float:
    score = 0.0
    for rule in rule_groups.values():
        hits = sum(1 for keyword in rule["keywords"] if keyword in text_lower)
        score += hits * float(rule.get("weight", 1.0))
    return score


def _pattern_score(text: str, compiled_groups: Dict) -> float:
    score = 0.0
    for rule in compiled_groups.values():
        hits = sum(1 for pattern in rule["patterns"] if pattern.search(text))
        score += hits * float(rule.get("weight", 1.0))
    return score


def _compile_rule_patterns(pattern_rules: Dict) -> Dict:
    return {
        label: {
            name: {
                "patterns": [re.compile(pattern, re.IGNORECASE) for pattern in rule["patterns"]],
                "weight": rule.get("weight", 1.0),
            }
            for name, rule in groups.items()
        }
        for label, groups in pattern_rules.items()
    }


def _rules_regex_boilerplate_probability(text: str, model: Dict) -> float:
    text = str(text)
    text_lower = text.lower()
    compiled_patterns = model["_compiled_patterns"]

    boilerplate_score = float(model.get("default_boilerplate_score", 0.2))
    substantive_score = float(model.get("default_substantive_score", 0.35))

    boilerplate_score += _keyword_score(text_lower, model["keyword_rules"]["boilerplate"])
    boilerplate_score += _pattern_score(text, compiled_patterns["boilerplate"])
    substantive_score += _keyword_score(text_lower, model["keyword_rules"]["substantive"])
    substantive_score += _pattern_score(text, compiled_patterns["substantive"])

    total = boilerplate_score + substantive_score
    if total <= 0:
        return 0.5
    return float(np.clip(boilerplate_score / total, 0.0, 1.0))


def train_rules_regex_model(feat_df: pd.DataFrame) -> Dict:
    return {
        "type": "rules_regex",
        "keyword_rules": RULE_KEYWORDS,
        "pattern_rules": RULE_PATTERNS,
        "default_boilerplate_score": 0.2,
        "default_substantive_score": 0.8,
    }


def predict_rules_regex_model(model: Dict, feat_df: pd.DataFrame) -> np.ndarray:
    if "_compiled_patterns" not in model:
        model["_compiled_patterns"] = _compile_rule_patterns(model["pattern_rules"])
    return np.asarray([_rules_regex_boilerplate_probability(text, model) for text in feat_df["sentence_text"]], dtype=float)


def train_linear_embedding_model(X: np.ndarray, y: np.ndarray, cfg: Dict) -> LogisticRegression:
    p = cfg["models"]["linear_embeddings"]
    model = LogisticRegression(C=float(p["C"]), max_iter=int(p["max_iter"]), class_weight=p["class_weight"])
    model.fit(X, y)
    return model


def train_tree_enriched_model(X: np.ndarray, y: np.ndarray, cfg: Dict):
    params = cfg["models"]["tree_enriched"]
    if params["estimator"] == "random_forest":
        p = params["random_forest"]
        model = RandomForestClassifier(n_estimators=int(p["n_estimators"]), max_depth=int(p["max_depth"]), min_samples_leaf=int(p["min_samples_leaf"]), n_jobs=int(p["n_jobs"]), random_state=int(p["random_state"]))
    else:
        p = params["histgbm"]
        model = HistGradientBoostingClassifier(max_depth=int(p["max_depth"]), learning_rate=float(p["learning_rate"]), max_iter=int(p["max_iter"]), random_state=int(p["random_state"]))
    model.fit(X, y)
    return model


def _clean_fasttext_text(text: str) -> str:
    return " ".join(str(text).replace("\n", " ").replace("\r", " ").split())


def _write_fasttext_training_file(train_df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for _, row in train_df.iterrows():
            label = row["label"]
            text = _clean_fasttext_text(row["sentence_text"])
            f.write(f"__label__{label} {text}\n")


def train_fasttext_model(train_df: pd.DataFrame, cfg: Dict, logger, train_path: Path | None = None, model_path: Path | None = None):
    try:
        import fasttext
    except Exception as exc:
        logger.warning("Skipping fastText because the fasttext package is unavailable: %s", exc)
        return None
    params = cfg["models"]["fasttext"]
    train_path = train_path or artifact_path(cfg, "models", "fasttext_train.txt")
    model_path = model_path or artifact_path(cfg, "models", "fasttext.bin")
    _write_fasttext_training_file(train_df, train_path)
    model = fasttext.train_supervised(
        input=str(train_path),
        lr=float(params["lr"]),
        epoch=int(params["epoch"]),
        wordNgrams=int(params["wordNgrams"]),
        dim=int(params["dim"]),
        minn=int(params["minn"]),
        maxn=int(params["maxn"]),
        loss=params.get("loss", "softmax"),
        thread=int(params.get("thread", 4)),
        verbose=int(params.get("verbose", 0)),
    )
    model.save_model(str(model_path))
    return {"path": model_path}


def apply_model_params(cfg: Dict, family: str, params: Dict) -> Dict:
    tuned = copy.deepcopy(cfg)
    for key, value in params.items():
        parts = key.split(".")
        target = tuned["models"][family]
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    return tuned


def cfg_with_best_hyperparams(cfg: Dict, logger) -> Dict:
    if not cfg["training"].get("use_grid_search_params", True):
        return cfg
    path = output_path(cfg, "grid_search", "best_hyperparams.json")
    if not path.exists():
        return cfg
    best = load_json(path)
    tuned = copy.deepcopy(cfg)
    for family, item in best.items():
        if family in tuned["models"]:
            tuned = apply_model_params(tuned, family, item.get("params", {}))
    logger.info("Loaded best hyperparameters from %s", path)
    return tuned


def predict_fasttext_model(model_path: Path, texts: List[str]) -> np.ndarray:
    import fasttext
    model = fasttext.load_model(str(model_path))
    cleaned = [_clean_fasttext_text(text) for text in texts]
    labels, probs = model.predict(cleaned, k=1)
    out = []
    for label_row, prob_row in zip(labels, probs):
        top_label = label_row[0].replace("__label__", "")
        top_prob = float(prob_row[0])
        out.append(top_prob if top_label == "boilerplate" else 1.0 - top_prob)
    return np.clip(np.asarray(out, dtype=float), 0.0, 1.0)


def _concat_enriched_features(feat_df: pd.DataFrame, emb: np.ndarray) -> np.ndarray:
    non_feature_cols = {"sentence_id", "split", "label", "sentence_text"}
    extra = feat_df[[c for c in feat_df.columns if c not in non_feature_cols]].to_numpy(dtype=float)
    return np.hstack([extra, emb])


def _train_finbert(train_df: pd.DataFrame, val_df: pd.DataFrame, cfg: Dict, logger, out_dir: Path | None = None):
    try:
        from datasets import Dataset
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, TrainingArguments, Trainer
    except Exception as exc:
        logger.warning("Skipping FinBERT because dependencies are unavailable: %s", exc)
        return None
    out_dir = out_dir or artifact_path(cfg, "models", "finbert")
    pretrained = cfg["models"]["finbert"]["pretrained_name"]
    tokenizer = AutoTokenizer.from_pretrained(pretrained)
    model = AutoModelForSequenceClassification.from_pretrained(
        pretrained,
        num_labels=2,
        id2label=INT_TO_LABEL,
        label2id=LABEL_TO_INT,
        ignore_mismatched_sizes=True,
    )

    def tokenize_fn(batch):
        return tokenizer(batch["sentence_text"], truncation=True, padding="max_length", max_length=128)

    train_data = train_df[["sentence_text", "y"]].rename(columns={"y": "labels"})
    val_data = val_df[["sentence_text", "y"]].rename(columns={"y": "labels"})
    train_ds = Dataset.from_pandas(train_data, preserve_index=False).map(tokenize_fn, batched=True)
    val_ds = Dataset.from_pandas(val_data, preserve_index=False).map(tokenize_fn, batched=True)
    args = TrainingArguments(output_dir=str(out_dir / "tmp"), num_train_epochs=float(cfg["models"]["finbert"]["num_train_epochs"]), per_device_train_batch_size=int(cfg["models"]["finbert"]["batch_size"]), per_device_eval_batch_size=int(cfg["models"]["finbert"]["batch_size"]), learning_rate=float(cfg["models"]["finbert"]["learning_rate"]), weight_decay=float(cfg["models"]["finbert"]["weight_decay"]), logging_steps=50, save_strategy="no", report_to=[])
    trainer_kwargs = {"model": model, "args": args, "train_dataset": train_ds, "eval_dataset": val_ds}
    try:
        Trainer(**trainer_kwargs, processing_class=tokenizer).train()
    except TypeError:
        Trainer(**trainer_kwargs).train()
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    save_json({"family": "finbert", "path": "models/finbert"}, out_dir / "metadata.json")
    return {"directory": str(out_dir)}


def _train_setfit(train_df: pd.DataFrame, cfg: Dict, logger, out_dir: Path | None = None):
    try:
        from datasets import Dataset
        from setfit import SetFitModel, Trainer, TrainingArguments
    except Exception as exc:
        logger.warning("Skipping SetFit because dependencies are unavailable: %s", exc)
        return None
    out_dir = out_dir or artifact_path(cfg, "models", "setfit")
    model = SetFitModel.from_pretrained(cfg["models"]["setfit"]["pretrained_name"])
    train_data = train_df[["sentence_text", "y"]].rename(columns={"sentence_text": "text", "y": "label"})
    train_ds = Dataset.from_pandas(train_data, preserve_index=False)
    args = TrainingArguments(
        output_dir=str(out_dir / "tmp"),
        batch_size=int(cfg["models"]["setfit"]["batch_size"]),
        num_iterations=int(cfg["models"]["setfit"]["num_iterations"]),
        num_epochs=int(cfg["models"]["setfit"]["num_epochs"]),
        body_learning_rate=float(cfg["models"]["setfit"]["learning_rate"]),
        report_to="none",
        save_strategy="no",
    )
    trainer = Trainer(model=model, args=args, train_dataset=train_ds)
    trainer.train()
    out_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(out_dir))
    save_json({"family": "setfit", "path": "models/setfit"}, out_dir / "metadata.json")
    return {"directory": str(out_dir)}


def _predict_proba_finbert(model_dir: Path, texts: List[str]) -> np.ndarray:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.eval()
    enc = tokenizer(texts, truncation=True, padding=True, max_length=128, return_tensors="pt")
    with torch.no_grad():
        logits = model(**enc).logits
    probs = torch.softmax(logits, dim=1).cpu().numpy()
    return probs[:, 1]


def _predict_proba_setfit(model_dir: Path, texts: List[str]) -> np.ndarray:
    from setfit import SetFitModel
    model = SetFitModel.from_pretrained(str(model_dir))
    probs = model.predict_proba(texts)
    return np.asarray(probs)[:, 1]


def _upsert_manifest_item(cfg: Dict, item: Dict) -> None:
    manifest_path = artifact_path(cfg, "models", "manifest.json")
    manifest = load_json(manifest_path) if manifest_path.exists() else []
    manifest = [existing for existing in manifest if existing["family"] != item["family"]]
    manifest.append(item)
    save_json(manifest, manifest_path)


def _train_family(family: str, cfg: Dict, logger, feat_df: pd.DataFrame, emb: np.ndarray, train_idx: np.ndarray, val_idx: np.ndarray, train_df: pd.DataFrame, val_df: pd.DataFrame) -> Dict | None:
    X_enriched = _concat_enriched_features(feat_df, emb) if family == "tree_enriched" else None
    if family == "rules_regex":
        save_pickle(train_rules_regex_model(feat_df), artifact_path(cfg, "models", "rules_regex.pkl"))
        return {"family": "rules_regex", "path": "models/rules_regex.pkl"}
    if family == "linear_embeddings":
        t0 = time.perf_counter(); model = train_linear_embedding_model(emb[train_idx], train_df["y"].to_numpy(), cfg); train_sec = time.perf_counter() - t0
        save_pickle(model, artifact_path(cfg, "models", "linear_embeddings.pkl"))
        return {"family": "linear_embeddings", "path": "models/linear_embeddings.pkl", "train_seconds": train_sec}
    if family == "tree_enriched":
        t0 = time.perf_counter(); model = train_tree_enriched_model(X_enriched[train_idx], train_df["y"].to_numpy(), cfg); train_sec = time.perf_counter() - t0
        save_pickle(model, artifact_path(cfg, "models", "tree_enriched.pkl"))
        return {"family": "tree_enriched", "path": "models/tree_enriched.pkl", "train_seconds": train_sec}
    if family == "fasttext":
        t0 = time.perf_counter(); model = train_fasttext_model(train_df, cfg, logger); train_sec = time.perf_counter() - t0
        if model is not None:
            return {"family": "fasttext", "path": "models/fasttext.bin", "train_seconds": train_sec}
        return None
    if family == "finbert":
        t0 = time.perf_counter(); model = _train_finbert(train_df, val_df, cfg, logger); train_sec = time.perf_counter() - t0
        if model is not None:
            return {"family": "finbert", "path": "models/finbert", "train_seconds": train_sec}
        return None
    if family == "setfit":
        t0 = time.perf_counter(); model = _train_setfit(train_df, cfg, logger); train_sec = time.perf_counter() - t0
        if model is not None:
            return {"family": "setfit", "path": "models/setfit", "train_seconds": train_sec}
        return None
    raise ValueError(f"Unsupported trainable family: {family}")


def _load_training_data(cfg: Dict):
    feat_df, emb = _load_feature_blocks(cfg)
    train_idx, val_idx, _ = _split_arrays(feat_df, emb)
    train_idx = np.concatenate([train_idx, val_idx])
    train_idx = np.sort(train_idx)
    train_df = feat_df.iloc[train_idx].copy()
    val_df = feat_df.iloc[val_idx].copy()
    train_df["y"] = _y_from_df(train_df)
    val_df["y"] = _y_from_df(val_df)
    return feat_df, emb, train_idx, val_idx, train_df, val_df


def train_one_family(cfg: Dict, logger, family: str) -> Dict | None:
    cfg = cfg_with_best_hyperparams(cfg, logger)
    if family == "ensemble":
        logger.info("Skipping train_one for ensemble; ensemble is built during evaluate")
        return None
    feat_df, emb, train_idx, val_idx, train_df, val_df = _load_training_data(cfg)
    item = _train_family(family, cfg, logger, feat_df, emb, train_idx, val_idx, train_df, val_df)
    if item is not None:
        _upsert_manifest_item(cfg, item)
        logger.info("Trained %s on train+val and updated manifest", family)
    return item


def train_all_families(cfg: Dict, logger) -> None:
    cfg = cfg_with_best_hyperparams(cfg, logger)
    feat_df, emb, train_idx, val_idx, train_df, val_df = _load_training_data(cfg)
    manifest = []
    families = cfg["training"]["benchmark_families"]
    for family in families:
        if family == "ensemble":
            continue
        item = _train_family(family, cfg, logger, feat_df, emb, train_idx, val_idx, train_df, val_df)
        if item is not None:
            manifest.append(item)
    
    save_json(manifest, artifact_path(cfg, "models", "manifest.json"))
    logger.info("Saved model manifest with %d families trained on train+val", len(manifest))


def predict_family_proba(cfg: Dict, family: str, feat_df: pd.DataFrame, emb: np.ndarray, texts: List[str] | None = None) -> np.ndarray:
    texts = texts or feat_df["sentence_text"].tolist()
    if family == "rules_regex":
        return predict_rules_regex_model(load_pickle(artifact_path(cfg, "models", "rules_regex.pkl")), feat_df)
    if family == "linear_embeddings":
        return load_pickle(artifact_path(cfg, "models", "linear_embeddings.pkl")).predict_proba(emb)[:, 1]
    if family == "tree_enriched":
        return load_pickle(artifact_path(cfg, "models", "tree_enriched.pkl")).predict_proba(_concat_enriched_features(feat_df, emb))[:, 1]
    if family == "fasttext":
        return predict_fasttext_model(artifact_path(cfg, "models", "fasttext.bin"), texts)
    if family == "finbert":
        return _predict_proba_finbert(artifact_path(cfg, "models", "finbert"), texts)
    if family == "setfit":
        return _predict_proba_setfit(artifact_path(cfg, "models", "setfit"), texts)
    raise ValueError(f"Unsupported family: {family}")
