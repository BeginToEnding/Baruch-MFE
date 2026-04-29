import re
import os
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import requests
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from .utils import cache_path, interim_path, read_parquet, save_parquet


REGEX_FEATURES = {
    "has_operator": r"\boperator\b",
    "has_greeting": r"\bgood morning\b|\bgood afternoon\b|\bgood evening\b|welcome to",
    "has_thank_you": r"\bthank you\b|\bthanks\b|thanks for joining|thank you for joining",
    "has_forward_looking": r"forward-looking statements?|safe harbor|actual results may differ",
    "has_non_gaap": r"non-gaap|non gaap",
    "has_sec": r"\bsec\b|10-k|10-q|8-k",
    "has_webcast_replay": r"webcast|audio cast|replay|recording|available on.*website",
    "has_investor_relations": r"investor relations|press release|earnings release|ir website",
    "has_next_question": r"next question|question comes from|take our next question|next caller",
    "has_turn_transition": r"turn it over|pass it over|hand it over|let me turn|now turn",
    "has_speaker_intro": r"\banalysts?\b|research analyst|joining me today|with me today|chief executive|chief financial",
    "has_slide_reference": r"\bslide\s+\d+\b|on the slide|in the appendix|supplemental materials",
    "has_dollar_amount": r"\$| billion| million",
    "has_percent": r"%|percent|basis points?\b|bps\b",
    "has_period_comparison": r"\bq[1-4]\b|quarter|year-over-year|year over year|sequential|prior year",
    "has_guidance_outlook": r"guidance|outlook|forecast|expect|expects|expected|we expect",
    "has_margin": r"margin|gross margin|operating margin",
    "has_revenue_earnings": r"\brevenue\b|sales|\beps\b|earnings per share|earnings",
    "has_cash_flow_capital": r"cash flow|free cash flow|operating cash|balance sheet|liquidity|debt|leverage|capex|capital expenditure|capital deployment",
    "has_strategy": r"strategy|strategic|priorities|initiative|roadmap",
    "has_demand_pricing": r"demand|pricing|pipeline|backlog|orders?|bookings?",
    "has_customer_product": r"customers?|clients?|product|platform|solution|enterprise",
    "has_segment_region": r"segment|division|business unit|geograph|region|international|domestic",
    "has_operations_supply": r"supply chain|inventory|capacity|utilization|production|manufacturing",
    "has_ai_cloud_data_center": r"\bai\b|artificial intelligence|cloud|data center|accelerator|gpu",
    "has_management_view": r"we believe|we think|we expect|we remain confident|we are confident|we feel",
    "has_action_verbs": r"launched|delivered|expanded|invested|acquired|reduced|improved|achieved|decided",
    "has_causal_explanation": r"\bbecause\b|due to|as a result|driven by|reflecting|primarily due",
    "has_business_question": r"\bcan you\b|\bcould you\b|\bwould you\b|\bhow do you\b|\bwhat are\b|\bwhat is\b|\bwhy\b|\bwhen\b|\bwhere\b",
    "has_qanda": r"question and answer|q&a|follow[- ]?up",
}



def compile_patterns() -> Dict[str, re.Pattern]:
    return {k: re.compile(v, re.IGNORECASE) for k, v in REGEX_FEATURES.items()}



def extract_regex_features(sentences: pd.Series) -> pd.DataFrame:
    patterns = compile_patterns()
    rows = []
    for sent in sentences:
        record = {name: int(bool(pattern.search(sent))) for name, pattern in patterns.items()}
        rows.append(record)
    return pd.DataFrame(rows)



def extract_surface_features(sentences: pd.Series) -> pd.DataFrame:
    rows = []
    for sent in sentences:
        digits = sum(ch.isdigit() for ch in sent)
        uppers = sum(ch.isupper() for ch in sent)
        punct = len(re.findall(r"[,:;()\-]", sent))
        words = sent.split()
        rows.append(
            {
                "char_len": len(sent),
                "token_len": len(words),
                "digit_count": digits,
                "upper_ratio": uppers / max(len(sent), 1),
                "punct_count": punct,
                "question_mark": int("?" in sent),
            }
        )
    return pd.DataFrame(rows)



def _normalize_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, 1e-12)


def encode_sentences(model_name: str, sentences: List[str], batch_size: int = 64, normalize: bool = True) -> np.ndarray:
    model = SentenceTransformer(model_name)
    emb = model.encode(sentences, batch_size=batch_size, show_progress_bar=True, normalize_embeddings=normalize)
    return np.asarray(emb)


def encode_sentences_ollama(model_name: str, sentences: List[str], batch_size: int = 64, normalize: bool = True) -> np.ndarray:
    base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    rows = []
    for start in tqdm(range(0, len(sentences), batch_size), desc=f"ollama:{model_name}"):
        batch = sentences[start : start + batch_size]
        payload = {"model": model_name, "input": batch}
        response = requests.post(f"{base_url}/api/embed", json=payload, timeout=180)
        response.raise_for_status()
        rows.extend(response.json()["embeddings"])
    emb = np.asarray(rows, dtype=np.float32)
    return _normalize_rows(emb) if normalize else emb


def encode_sentences_from_config(cfg: Dict, sentences: List[str]) -> np.ndarray:
    provider = cfg["features"].get("embedding_provider", "sentence_transformers")
    model_name = cfg["features"]["sentence_embedding_model"]
    batch_size = int(cfg["features"]["embedding_batch_size"])
    normalize = bool(cfg["features"].get("normalize_embeddings", True))
    if provider == "sentence_transformers":
        return encode_sentences(model_name, sentences, batch_size=batch_size, normalize=normalize)
    if provider == "ollama":
        return encode_sentences_ollama(model_name, sentences, batch_size=batch_size, normalize=normalize)
    raise ValueError(f"Unsupported embedding provider: {provider}")



def build_feature_cache(cfg: Dict, logger) -> None:
    gold = read_parquet(interim_path(cfg, "gold_final.parquet"))
    sentences = gold["sentence_text"].tolist()
    
    regex_df = extract_regex_features(gold["sentence_text"])
    surface_df = extract_surface_features(gold["sentence_text"])
    feature_df = pd.concat([gold[["sentence_id", "split", "label", "sentence_text"]].reset_index(drop=True), regex_df, surface_df], axis=1)
    save_parquet(feature_df, interim_path(cfg, "features_regex.parquet"))
    logger.info("Saved regex+surface features")

    if cfg["features"]["use_embeddings"]:
        embeddings = encode_sentences_from_config(cfg, sentences)
        np.save(cache_path(cfg, "embeddings_all.npy"), embeddings)
        logger.info("Saved embeddings to cache")
