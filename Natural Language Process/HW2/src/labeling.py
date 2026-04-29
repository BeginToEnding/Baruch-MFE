import json
import os
import re
import hashlib
import time
from typing import Any, Dict, List

import pandas as pd
import requests
from anthropic import Anthropic
from openai import OpenAI
from tqdm import tqdm

from .rubric import LABELING_RUBRIC
from .utils import interim_path, read_parquet, save_json, save_parquet


VALID_LABELS = {"boilerplate", "substantive"}


def _safe_parse_json(text: str) -> Any:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        candidates = [(text.find("{"), text.rfind("}")), (text.find("["), text.rfind("]"))]
        for start, end in candidates:
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise


def _read_audit_csv(path) -> pd.DataFrame:
    last_exc = None
    for encoding in ["utf-8-sig", "utf-8", "gbk", "latin1"]:
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_exc = exc
    raise last_exc


def _build_batch_prompt(records: List[Dict], validation_error: str | None = None) -> str:
    payload = [{"sentence_id": int(r["sentence_id"]), "sentence_text": r["sentence_text"]} for r in records]
    retry_note = ""
    if validation_error:
        retry_note = f"\n\nYour previous response was invalid because: {validation_error}\nTry again and fix only the JSON format."
    return (
        f"{LABELING_RUBRIC}\n\n"
        "Label each sentence independently. Return ONLY valid JSON in exactly this shape:\n"
        "{\n"
        '  "results": [\n'
        '    {"sentence_id": 123, "label": "boilerplate", "reason": "short explanation"}\n'
        "  ]\n"
        "}\n\n"
        "Requirements:\n"
        "- Include exactly one result for every input sentence_id.\n"
        "- Do not add sentence_ids that were not provided.\n"
        '- Each label must be either "boilerplate" or "substantive".\n'
        "- Keep each reason short.\n"
        f"{retry_note}\n\n"
        f"Sentences:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _slug(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    return slug or "judge"


def judge_run_id(judge_cfg: Dict) -> str:
    return _slug(judge_cfg["name"])


def judge_label_col(judge_cfg: Dict) -> str:
    return f"judge_label_{judge_run_id(judge_cfg)}"


def judge_reason_col(judge_cfg: Dict) -> str:
    return f"judge_reason_{judge_run_id(judge_cfg)}"


def current_judge_label_cols(cfg: Dict, df: pd.DataFrame | None = None) -> list[str]:
    cols = []
    for judge in cfg["labeling"]["judges"]:
        if not judge.get("enabled", True):
            continue
        col = judge_label_col(judge)
        if (df is None or col in df.columns) and col not in cols:
            cols.append(col)
    return cols


def _current_judge_cols(cfg: Dict) -> set[str]:
    cols = set()
    for judge in cfg["labeling"]["judges"]:
        if not judge.get("enabled", True):
            continue
        cols.add(judge_label_col(judge))
        cols.add(judge_reason_col(judge))
    return cols


def _drop_inactive_judge_columns(df: pd.DataFrame, cfg: Dict) -> pd.DataFrame:
    active_cols = _current_judge_cols(cfg)
    stale_cols = [
        c
        for c in df.columns
        if (c.startswith("judge_label_") or c.startswith("judge_reason_")) and c not in active_cols
    ]
    return df.drop(columns=stale_cols)


def _judge_manifest(cfg: Dict) -> list[Dict]:
    manifest = []
    for judge in cfg["labeling"]["judges"]:
        if not judge.get("enabled", True):
            continue
        manifest.append({
            "name": judge["name"],
            "provider": judge["provider"],
            "model": judge["model"],
            "run_id": judge_run_id(judge),
            "label_col": judge_label_col(judge),
            "reason_col": judge_reason_col(judge),
        })
    return manifest


def _judge_signature(cfg: Dict) -> str:
    payload = json.dumps(_judge_manifest(cfg), sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _call_openai(model: str, records: List[Dict], judge_cfg: Dict, validation_error: str | None = None) -> Any:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.responses.create(
        model=model,
        input=_build_batch_prompt(records, validation_error),
        temperature=float(judge_cfg.get("temperature", 0)),
    )
    return _safe_parse_json(response.output_text)


def _call_anthropic(model: str, records: List[Dict], judge_cfg: Dict, validation_error: str | None = None) -> Any:
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=model,
        max_tokens=int(judge_cfg.get("max_tokens", 2048)),
        temperature=float(judge_cfg.get("temperature", 0)),
        messages=[{"role": "user", "content": _build_batch_prompt(records, validation_error)}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "text", None))
    return _safe_parse_json(text)


def _ollama_default_think(model: str) -> bool | None:
    model_name = model.lower()
    if "qwen" in model_name or "gemma" in model_name:
        return False
    return None


def _call_ollama(model: str, records: List[Dict], judge_cfg: Dict, validation_error: str | None = None) -> Any:
    base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    options = {"temperature": 0}
    options.update(judge_cfg.get("options", {}))
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _build_batch_prompt(records, validation_error)}],
        "stream": False,
        "options": options,
    }
    think = judge_cfg.get("think", _ollama_default_think(model))
    if think is not None:
        payload["think"] = bool(think)
    if "format" in judge_cfg:
        payload["format"] = judge_cfg["format"]
    r = requests.post(f"{base_url}/api/chat", json=payload, timeout=float(judge_cfg.get("timeout_seconds", 180)))
    r.raise_for_status()
    return _safe_parse_json(r.json()["message"]["content"])


def _dispatch_judge(judge_cfg: Dict, records: List[Dict], validation_error: str | None = None) -> Any:
    provider = judge_cfg["provider"]
    model = judge_cfg["model"]
    if provider == "openai":
        return _call_openai(model, records, judge_cfg, validation_error)
    if provider == "anthropic":
        return _call_anthropic(model, records, judge_cfg, validation_error)
    if provider == "ollama":
        return _call_ollama(model, records, judge_cfg, validation_error)
    raise ValueError(f"Unsupported provider: {provider}")


def _validate_batch_response(parsed: Any, expected_ids: set[int]) -> Dict[int, Dict[str, str]]:
    if isinstance(parsed, dict):
        results = parsed.get("results")
    elif isinstance(parsed, list):
        results = parsed
    else:
        raise ValueError("response must be a JSON object with results or a JSON list")
    if not isinstance(results, list):
        raise ValueError("results must be a list")

    output = {}
    for item in results:
        if not isinstance(item, dict):
            raise ValueError("each result must be an object")
        if "sentence_id" not in item:
            raise ValueError("each result must include sentence_id")
        try:
            sentence_id = int(item["sentence_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid sentence_id: {item.get('sentence_id')}") from exc
        if sentence_id not in expected_ids:
            raise ValueError(f"unexpected sentence_id: {sentence_id}")
        if sentence_id in output:
            raise ValueError(f"duplicate sentence_id: {sentence_id}")
        label = item.get("label")
        if label not in VALID_LABELS:
            raise ValueError(f"invalid label for sentence_id={sentence_id}: {label}")
        reason = item.get("reason", "")
        if reason is None:
            reason = ""
        if not isinstance(reason, str):
            reason = str(reason)
        output[sentence_id] = {"label": label, "reason": reason}

    missing = expected_ids - set(output)
    if missing:
        raise ValueError(f"missing sentence_ids: {sorted(missing)[:10]}")
    return output


def _label_records_with_retries(records: List[Dict], judge_cfg: Dict, logger) -> Dict[int, Dict[str, str]]:
    max_retries = int(judge_cfg.get("max_retries", 3))
    expected_ids = {int(r["sentence_id"]) for r in records}
    validation_error = None
    for attempt in range(1, max_retries + 1):
        try:
            parsed = _dispatch_judge(judge_cfg, records, validation_error)
            return _validate_batch_response(parsed, expected_ids)
        except Exception as exc:
            validation_error = str(exc)
            logger.warning(
                "Judge %s batch failed attempt=%d size=%d: %s",
                judge_cfg["name"],
                attempt,
                len(records),
                exc,
            )
            time.sleep(1.5 * attempt)
    raise ValueError(validation_error or "batch labeling failed")


def _run_single_judge(df: pd.DataFrame, judge_cfg: Dict, logger) -> pd.DataFrame:
    judge_name = judge_cfg["name"]
    model = judge_cfg["model"]
    label_col = judge_label_col(judge_cfg)
    reason_col = judge_reason_col(judge_cfg)
    if label_col not in df.columns:
        df[label_col] = None
    if reason_col not in df.columns:
        df[reason_col] = None
    if judge_cfg.get("rerun_existing", False):
        df[label_col] = None
        df[reason_col] = None
    rows = df[df[label_col].isna()].copy()
    logger.info("Judge %s (%s) labeling %d remaining rows", judge_name, model, len(rows))
    batch_size = max(1, int(judge_cfg.get("batch_size", 1)))
    row_items = list(rows.iterrows())
    for start in tqdm(range(0, len(row_items), batch_size), desc=judge_name):
        batch_items = row_items[start : start + batch_size]
        records = [
            {"sentence_id": int(row["sentence_id"]), "sentence_text": row["sentence_text"]}
            for _, row in batch_items
        ]
        try:
            results = _label_records_with_retries(records, judge_cfg, logger)
        except Exception as exc:
            logger.warning("Judge %s batch failed after retries; falling back to single-sentence retries: %s", judge_name, exc)
            results = {}
            for _, row in batch_items:
                record = {"sentence_id": int(row["sentence_id"]), "sentence_text": row["sentence_text"]}
                try:
                    results.update(_label_records_with_retries([record], judge_cfg, logger))
                except Exception as single_exc:
                    logger.warning("Judge %s failed sentence_id=%s after fallback: %s", judge_name, row["sentence_id"], single_exc)
                    results[int(row["sentence_id"])] = {"label": "error", "reason": "judge_failed"}
        for idx, row in batch_items:
            result = results.get(int(row["sentence_id"]), {"label": "error", "reason": "judge_failed"})
            df.at[idx, label_col] = result["label"]
            df.at[idx, reason_col] = result.get("reason", "")
    return df


def run_labeling_pipeline(cfg: Dict, logger) -> pd.DataFrame:
    gold_path = interim_path(cfg, "gold_candidates.parquet")
    out_path = interim_path(cfg, "judge_outputs.parquet")
    df = read_parquet(out_path) if out_path.exists() else read_parquet(gold_path)
    keep_inactive = bool(cfg["labeling"].get("keep_inactive_judge_labels", True))
    if not keep_inactive:
        df = _drop_inactive_judge_columns(df, cfg)
    save_json(_judge_manifest(cfg), interim_path(cfg, "judge_manifest.json"))
    for judge in cfg["labeling"]["judges"]:
        if not judge.get("enabled", True):
            continue
        judge = dict(judge)
        judge.setdefault("max_retries", cfg["labeling"].get("max_retries", 3))
        judge.setdefault("batch_size", cfg["labeling"].get("batch_size", 1))
        judge.setdefault("rerun_existing", cfg["labeling"].get("rerun_existing_judges", False))
        df = _run_single_judge(df, judge, logger)
        save_parquet(df, out_path)
        logger.info("Checkpointed judge outputs to %s", out_path)
    return df


def build_audit_sample(cfg: Dict, logger) -> pd.DataFrame:
    src = read_parquet(interim_path(cfg, "judge_outputs.parquet"))
    judge_cols = current_judge_label_cols(cfg, src)
    src["vote_count_boilerplate"] = (src[judge_cols] == "boilerplate").sum(axis=1)
    src["vote_count_substantive"] = (src[judge_cols] == "substantive").sum(axis=1)
    src["is_disagreement"] = ~((src["vote_count_boilerplate"] == 0) | (src["vote_count_substantive"] == 0))
    
    frac = float(cfg["labeling"].get("sample_audit_fraction", 0.15))
    seed = int(cfg["project"]["random_seed"])
    disagreement = src[src["is_disagreement"]].copy()
    agreement = src[~src["is_disagreement"]].copy()
    n_dis = min(len(disagreement), max(1, int(len(disagreement) * 0.8)) if len(disagreement) else 0)
    n_agr = min(len(agreement), max(1, int(len(src) * frac) - n_dis)) if len(agreement) else 0
    sample_parts = []
    if n_dis > 0:
        sample_parts.append(disagreement.sample(n=n_dis, random_state=seed))
    if n_agr > 0:
        sample_parts.append(agreement.sample(n=n_agr, random_state=seed))
    audit = pd.concat(sample_parts, ignore_index=True) if sample_parts else src.head(0).copy()
    reason_cols = [c.replace("judge_label_", "judge_reason_", 1) for c in judge_cols if c.replace("judge_label_", "judge_reason_", 1) in audit.columns]
    base_cols = [c for c in ["sentence_id", "doc_id", "sentence_text", "vote_count_boilerplate", "vote_count_substantive", "is_disagreement"] if c in audit.columns]
    audit = audit[base_cols + judge_cols + reason_cols].copy()
    audit["audit_override_label"] = ""
    audit["audit_note"] = ""
    audit["audit_judge_signature"] = _judge_signature(cfg)
    out = interim_path(cfg, "audit_sample.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(out, index=False, encoding="utf-8-sig")
    logger.info("Saved audit sample with %d rows to %s", len(audit), out)
    return audit


def _find_judge_col_by_provider(cfg: Dict, df: pd.DataFrame, provider: str) -> str:
    matches = []
    for judge in cfg["labeling"]["judges"]:
        if judge.get("enabled", True) and judge["provider"] == provider:
            col = judge_label_col(judge)
            if col in df.columns:
                matches.append(col)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one current {provider} judge column, found {len(matches)}: {matches}")
    return matches[0]


def build_openai_anthropic_disagreement_audit(cfg: Dict, logger) -> pd.DataFrame:
    src = _read_audit_csv(interim_path(cfg, "audit_sample.csv"))
    openai_col = _find_judge_col_by_provider(cfg, src, "openai")
    anthropic_col = _find_judge_col_by_provider(cfg, src, "anthropic")
    valid = src[openai_col].isin(VALID_LABELS) & src[anthropic_col].isin(VALID_LABELS)
    disagreement = src[valid & (src[openai_col] != src[anthropic_col])].copy()
    reason_cols = [
        c.replace("judge_label_", "judge_reason_", 1)
        for c in [openai_col, anthropic_col]
        if c.replace("judge_label_", "judge_reason_", 1) in disagreement.columns
    ]
    base_cols = [c for c in ["sentence_id", "doc_id", "sentence_text"] if c in disagreement.columns]
    audit = disagreement[base_cols + [openai_col, anthropic_col] + reason_cols].copy()
    audit["audit_override_label"] = ""
    audit["audit_note"] = ""
    out = interim_path(cfg, "audit_sample_openai_anthropic_disagreements.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(out, index=False, encoding="utf-8-sig")
    logger.info("Saved %d OpenAI/Anthropic disagreement rows from audit_sample.csv to %s", len(audit), out)
    return audit


def merge_openai_anthropic_disagreement_audit(cfg: Dict, logger) -> pd.DataFrame:
    small_path = interim_path(cfg, "audit_sample_openai_anthropic_disagreements.csv")
    full_path = interim_path(cfg, "audit_sample.csv")
    small = _read_audit_csv(small_path)
    full = _read_audit_csv(full_path)
    full_ids = set(full["sentence_id"].astype(str))
    small["sentence_id"] = small["sentence_id"].astype(str)
    in_full = small["sentence_id"].isin(full_ids)
    dropped = int((~in_full).sum())
    if dropped:
        small = small[in_full].copy()
        small.to_csv(small_path, index=False, encoding="utf-8-sig")
        logger.info("Removed %d disagreement rows not present in audit_sample.csv from %s", dropped, small_path)

    update_cols = ["sentence_id", "audit_override_label", "audit_note"]
    updates = small[
        small["audit_override_label"].astype(str).str.strip().isin(VALID_LABELS)
    ][update_cols].copy()
    updates["audit_override_label"] = updates["audit_override_label"].astype(str).str.strip()
    updates = updates.drop_duplicates(subset=["sentence_id"], keep="last")

    merged = full.copy()
    for col in ["audit_override_label", "audit_note"]:
        if col not in merged.columns:
            merged[col] = ""
        merged[col] = merged[col].fillna("").astype(str)

    if not updates.empty:
        updates = updates.set_index("sentence_id")
        matched = merged["sentence_id"].astype(str).isin(updates.index)
        for col in ["audit_override_label", "audit_note"]:
            merged.loc[matched, col] = merged.loc[matched, "sentence_id"].astype(str).map(updates[col]).fillna("")

    merged.to_csv(full_path, index=False, encoding="utf-8-sig")
    logger.info("Merged %d reviewed disagreement overrides into %s", len(updates), full_path)
    return merged
