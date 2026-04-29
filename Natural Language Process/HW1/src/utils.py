from __future__ import annotations
import json
import logging
import hashlib
from pathlib import Path
from typing import Any
import yaml
import pandas as pd

def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")

def write_text(text: str, path: str | Path) -> None:
    Path(path).write_text(text, encoding="utf-8")

def read_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(obj: dict, path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def write_parquet(df: pd.DataFrame, path: str | Path) -> None:
    ensure_dir(Path(path).parent)
    df.to_parquet(path, index=False)

def read_parquet(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)

def stable_hash_dict(d: dict) -> str:
    payload = json.dumps(d, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()

def setup_logger(log_path: str | Path) -> logging.Logger:
    ensure_dir(Path(log_path).parent)
    logger = logging.getLogger("earnings_call_project")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    return logger

def remove_think_blocks(raw_text: str) -> str:
    import re
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)
    raw_text = re.sub(r"```json\s*", "", raw_text, flags=re.IGNORECASE)
    raw_text = raw_text.replace("```", "")
    return raw_text.strip()

def extract_json_block(raw_text: str) -> str:
    raw_text = remove_think_blocks(raw_text)
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start >= 0 and end > start:
        return raw_text[start:end+1]
    return raw_text

def repair_common_json_issues(raw_text: str) -> str:
    import re
    text = extract_json_block(raw_text)
    text = text.replace("\u2019", "'")
    text = re.sub(r",\s*([}\]])", r"\1", text)
    text = text.replace(": True", ": true").replace(": False", ": false").replace(": None", ": null")
    return text

def safe_load_json(raw_text: str) -> dict | None:
    text = repair_common_json_issues(raw_text)
    try:
        return json.loads(text)
    except Exception:
        return None

def normalize_theme(theme: str) -> str:
    if not isinstance(theme, str):
        return ""
    t = theme.strip().lower()
    aliases = {
        "ai pcs": "ai",
        "gen ai": "ai",
        "generative ai": "ai",
        "guidance raise": "guidance",
    }
    return aliases.get(t, t)

def next_trading_day(price_index: pd.Series, date) -> pd.Timestamp | None:
    d0 = pd.Timestamp(date).normalize()
    candidates = price_index[price_index > d0]
    if len(candidates) == 0:
        return None
    return pd.Timestamp(candidates.iloc[0]).normalize()
