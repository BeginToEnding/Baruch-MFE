import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
import yaml
from dotenv import load_dotenv


load_dotenv()


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    return logging.getLogger("bp_classifier")



def load_config(path: str | os.PathLike[str]) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    seed = int(cfg["project"]["random_seed"])
    random.seed(seed)
    np.random.seed(seed)
    return cfg



def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p



def ensure_project_dirs(cfg: Dict[str, Any]) -> None:
    for key in ["raw_transcripts_dir", "interim_dir", "cache_dir", "artifacts_dir", "outputs_dir"]:
        ensure_dir(cfg["paths"][key])
    ensure_dir(Path(cfg["paths"]["artifacts_dir"]) / "models")
    ensure_dir(Path(cfg["paths"]["artifacts_dir"]) / "best_model")
    ensure_dir(Path(cfg["paths"]["artifacts_dir"]) / "figures")
    outputs = Path(cfg["paths"]["outputs_dir"])
    for subdir in ["grid_search", "thresholds", "evaluation", "error_analysis"]:
        ensure_dir(outputs / subdir)



def save_parquet(df: pd.DataFrame, path: str | Path) -> None:
    ensure_dir(Path(path).parent)
    df.to_parquet(path, index=False)



def read_parquet(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)



def save_json(obj: Any, path: str | Path) -> None:
    ensure_dir(Path(path).parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)



def load_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)



def save_pickle(obj: Any, path: str | Path) -> None:
    ensure_dir(Path(path).parent)
    joblib.dump(obj, path)



def load_pickle(path: str | Path) -> Any:
    return joblib.load(path)



def get_path(cfg: Dict[str, Any], *parts: str) -> Path:
    return Path(*parts)



def interim_path(cfg: Dict[str, Any], filename: str) -> Path:
    return Path(cfg["paths"]["interim_dir"]) / filename



def cache_path(cfg: Dict[str, Any], filename: str) -> Path:
    return Path(cfg["paths"]["cache_dir"]) / filename



def artifact_path(cfg: Dict[str, Any], *parts: str) -> Path:
    return Path(cfg["paths"]["artifacts_dir"]).joinpath(*parts)



def output_path(cfg: Dict[str, Any], *parts: str) -> Path:
    return Path(cfg["paths"]["outputs_dir"]).joinpath(*parts)
