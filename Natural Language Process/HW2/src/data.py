import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List

import nltk
import pandas as pd
from sklearn.model_selection import train_test_split

from .utils import interim_path, read_parquet, save_parquet

try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    pass


def clean_transcript_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_transcript_marker(line: str) -> bool:
    return line.strip() in {
        "Presentation Operator Message",
        "Question and Answer Operator Message",
        "Question",
        "Answer",
        "Operator",
    }


def _is_speaker_or_title_line(line: str) -> bool:
    line = line.strip()
    return bool(re.match(r"^(Analysts|Executives|Company Participants|Conference Call Participants)\s+-\s+", line))


def deduplicate_lines(text: str) -> str:
    seen, kept = set(), []
    for line in text.splitlines():
        norm = line.strip()
        if not norm:
            kept.append("")
            continue
        if _is_transcript_marker(norm) or _is_speaker_or_title_line(norm):
            kept.append(line)
            continue
        if norm in seen:
            continue
        seen.add(norm)
        kept.append(line)
    return "\n".join(kept)


def _split_abbreviation_sentence_boundaries(sentence: str) -> List[str]:
    boundary = re.compile(
        r"\b((?:U\.S|U\.K|E\.U|D\.C)\.)\s+"
        r"((?:Now|And|But|So|We|I|It|This|That|The|In|On|Our|They|You|As|For|With)\b)"
    )
    marked = boundary.sub(r"\1\n\2", sentence)
    return [part.strip() for part in marked.split("\n") if part.strip()]


def sentence_tokenize(paragraph: str) -> List[str]:
    sentences = []
    for sent in nltk.sent_tokenize(paragraph):
        sentences.extend(_split_abbreviation_sentence_boundaries(sent))
    return sentences


def transcript_segments(text: str) -> List[str]:
    segments: List[str] = []
    current: List[str] = []
    pending_operator_header: List[str] = []

    def flush_current() -> None:
        if current:
            segments.append(" ".join(current).strip())
            current.clear()

    def flush_pending_header() -> None:
        if pending_operator_header:
            segments.append(" ".join(pending_operator_header).strip())
            pending_operator_header.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_current()
            flush_pending_header()
            continue

        if _is_transcript_marker(line):
            flush_current()
            if line.endswith("Operator Message"):
                flush_pending_header()
                pending_operator_header.append(line)
            elif pending_operator_header and line == "Operator":
                pending_operator_header.append(line)
                flush_pending_header()
            else:
                flush_pending_header()
                segments.append(line)
            continue

        flush_pending_header()
        if _is_speaker_or_title_line(line):
            flush_current()
            segments.append(line)
            continue

        current.append(line)

    flush_current()
    flush_pending_header()
    return [seg for seg in segments if seg]


def _slug(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    return slug or "judge"


def _judge_label_col(judge_cfg: Dict) -> str:
    return f"judge_label_{_slug(judge_cfg['name'])}"


def current_judge_label_cols(cfg: Dict, df: pd.DataFrame | None = None) -> List[str]:
    cols = []
    for judge in cfg["labeling"]["judges"]:
        if not judge.get("enabled", True):
            continue
        col = _judge_label_col(judge)
        if (df is None or col in df.columns) and col not in cols:
            cols.append(col)
    return cols


def _current_judge_manifest(cfg: Dict) -> List[Dict]:
    manifest = []
    for judge in cfg["labeling"]["judges"]:
        if not judge.get("enabled", True):
            continue
        label_col = _judge_label_col(judge)
        manifest.append({
            "name": judge["name"],
            "provider": judge["provider"],
            "model": judge["model"],
            "run_id": label_col.removeprefix("judge_label_"),
            "label_col": label_col,
            "reason_col": label_col.replace("judge_label_", "judge_reason_", 1),
        })
    return manifest


def _judge_signature(cfg: Dict) -> str:
    payload = json.dumps(_current_judge_manifest(cfg), sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _read_audit_csv(path) -> pd.DataFrame:
    last_exc = None
    for encoding in ["utf-8-sig", "utf-8", "gbk", "latin1"]:
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_exc = exc
    raise last_exc


def build_sentence_pool(cfg: Dict, logger) -> pd.DataFrame:
    raw_dir = Path(cfg["paths"]["raw_transcripts_dir"])
    min_chars = int(cfg["project"]["min_sentence_chars"])
    records, sentence_idx = [], 0
    for txt_file in sorted(raw_dir.glob("*.txt")):
        text = clean_transcript_text(txt_file.read_text(encoding="utf-8", errors="ignore"))
        if cfg["sentence_pool"]["deduplicate_lines"]:
            text = deduplicate_lines(text)
        segments = transcript_segments(text)
        for para_idx, para in enumerate(segments):
            for sent_in_para_idx, sent in enumerate(sentence_tokenize(para)):
                sent = re.sub(r"\s+", " ", sent).strip()
                if len(sent) < min_chars:
                    continue
                records.append({
                    "sentence_id": sentence_idx,
                    "doc_id": txt_file.stem,
                    "source_path": str(txt_file),
                    "paragraph_id": para_idx,
                    "sentence_in_paragraph": sent_in_para_idx,
                    "sentence_text": sent,
                    "char_len": len(sent),
                })
                sentence_idx += 1
    
    df = pd.DataFrame(records).drop_duplicates(subset=["doc_id", "sentence_text"]).reset_index(drop=True)
    out = interim_path(cfg, cfg["sentence_pool"]["output_file"])
    save_parquet(df, out)
    logger.info("Saved sentence pool with %d rows to %s", len(df), out)
    return df


def sample_gold_candidates(cfg: Dict, logger) -> pd.DataFrame:
    sentence_pool = read_parquet(interim_path(cfg, cfg["sentence_pool"]["output_file"]))
    n = min(int(cfg["labeling"]["gold_sample_size"]), len(sentence_pool))
    sampled = sentence_pool.sample(n=n, random_state=int(cfg["project"]["random_seed"])).copy()
    sampled["gold_candidate"] = True
    out = interim_path(cfg, "gold_candidates.parquet")
    save_parquet(sampled, out)
    logger.info("Saved %d gold candidates to %s", len(sampled), out)
    return sampled


def majority_vote(row: pd.Series, judge_cols: List[str]) -> str:
    if isinstance(row.get("audit_override_label"), str) and row.get("audit_override_label").strip() in {"boilerplate", "substantive"}:
        return row.get("audit_override_label").strip()
    votes = [row[c] for c in judge_cols]
    valid = [v for v in votes if v in {"boilerplate", "substantive"}]
    if not valid:
        return "unlabeled"
    counts = pd.Series(valid).value_counts()
    return counts.index[0]


def finalize_gold_labels_and_splits(cfg: Dict, logger) -> pd.DataFrame:
    df = read_parquet(interim_path(cfg, "judge_outputs.parquet"))
    audit_csv = interim_path(cfg, "audit_sample.csv")
    if audit_csv.exists():
        audit = _read_audit_csv(audit_csv)
        can_use_audit = "audit_override_label" in audit.columns
        if cfg["labeling"].get("require_current_audit_signature", True):
            current_signature = _judge_signature(cfg)
            can_use_audit = (
                can_use_audit
                and "audit_judge_signature" in audit.columns
                and audit["audit_judge_signature"].dropna().eq(current_signature).all()
            )
            if not can_use_audit:
                logger.warning("Ignoring audit overrides because %s was not generated for the current judge config", audit_csv)
        if can_use_audit:
            audit = audit[["sentence_id", "audit_override_label", "audit_note"]].copy()
            df = df.merge(audit, on="sentence_id", how="left")
    judge_cols = current_judge_label_cols(cfg, df)
    df["vote_count_boilerplate"] = (df[judge_cols] == "boilerplate").sum(axis=1)
    df["vote_count_substantive"] = (df[judge_cols] == "substantive").sum(axis=1)
    df["label"] = df.apply(lambda row: majority_vote(row, judge_cols), axis=1)
    df["is_disagreement"] = ~((df["vote_count_boilerplate"] == 0) | (df["vote_count_substantive"] == 0))
    labeled = df[df["label"].isin(["boilerplate", "substantive"])].copy()
    
    X = labeled[["sentence_id"]]
    y = labeled["label"]
    train_ratio = float(cfg["labeling"]["split_train"])
    val_ratio = float(cfg["labeling"]["split_val"])
    test_ratio = float(cfg["labeling"]["split_test"])
    seed = int(cfg["project"]["random_seed"])
    train_ids, temp_ids, _, y_temp = train_test_split(X, y, test_size=(1.0 - train_ratio), stratify=y, random_state=seed)
    relative_test = test_ratio / (val_ratio + test_ratio)
    val_ids, test_ids, _, _ = train_test_split(temp_ids, y_temp, test_size=relative_test, stratify=y_temp, random_state=seed)

    labeled["split"] = "train"
    labeled.loc[labeled["sentence_id"].isin(val_ids["sentence_id"]), "split"] = "val"
    labeled.loc[labeled["sentence_id"].isin(test_ids["sentence_id"]), "split"] = "test"
    out = interim_path(cfg, "gold_final.parquet")
    save_parquet(labeled, out)
    logger.info("Saved final gold labels with %d rows to %s", len(labeled), out)
    return labeled
