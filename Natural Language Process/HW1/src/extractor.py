from __future__ import annotations
from pathlib import Path
from src.llm_client import LLMClientFactory
from src.prompts import build_unified_messages
from src.schemas import validate_unified
from src.utils import write_text, write_json, safe_load_json, ensure_dir


class Extractor:
    def __init__(self, llm_cfg: dict, prompt_cfg: dict, raw_dir: str | Path, json_dir: str | Path):
        self.client = LLMClientFactory.create(llm_cfg)
        self.llm_cfg = llm_cfg
        self.prompt_cfg = prompt_cfg
        self.raw_dir = ensure_dir(raw_dir)
        self.json_dir = ensure_dir(json_dir)

    def _save_paths(self, record: dict) -> tuple[Path, Path]:
        base = f"{record['ticker']}_{record['quarter']}_unified"
        return self.raw_dir / f"{base}.txt", self.json_dir / f"{base}.json"

    def extract_unified(self, record: dict) -> dict:
        raw_path, json_path = self._save_paths(record)
        messages = build_unified_messages(record, self.prompt_cfg)
        raw_text = self.client.generate(messages, **self.llm_cfg)
        write_text(raw_text, raw_path)

        obj = safe_load_json(raw_text) or {}
        obj = validate_unified(obj)
        obj["_meta"] = {
            "ticker": record["ticker"],
            "quarter": record["quarter"],
            "call_date": record.get("call_date"),
            "company": record.get("company", ""),
            "raw_path": record.get("raw_path", ""),
        }
        write_json(obj, json_path)
        return obj
