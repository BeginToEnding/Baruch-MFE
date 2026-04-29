import re
from typing import Dict, List, Tuple

import nltk
import numpy as np
import pandas as pd

from .features import encode_sentences_from_config, extract_regex_features, extract_surface_features
from .models import INT_TO_LABEL, predict_family_proba
from .utils import artifact_path, load_json


CALL_MARKERS = {
    "Presentation Operator Message",
    "Question and Answer Operator Message",
    "Question",
    "Answer",
    "Operator",
}

INLINE_CALL_MARKER_RE = re.compile(
    r"\b(Presentation Operator Message|Question and Answer Operator Message|Question|Answer|Operator)\b"
)

ROLE_LINE_RE = re.compile(r"^(Analysts|Executives)\s+-\s+", re.IGNORECASE)
CALL_BOILERPLATE_RE = re.compile(
    r"^(?:"
    r"(?:our|the)?\s*next question(?:\s+is|\s+will come|\s+comes)?\s+(?:from|will come from)|"
    r"we(?:'ll| will)\s+take\s+(?:our\s+)?next question|"
    r"good (?:morning|afternoon|evening).*welcome|"
    r"\[?operator instructions\]?"
    r")",
    re.IGNORECASE,
)

INLINE_ROLE_RE = re.compile(
    r"^(?P<header>(?:Analysts|Executives)\s+-\s+"
    r".*?(?:Analyst|Team|Research|Officer|CEO|CFO|COO|Chairman|President|Founder|Director|Manager|Relations|Strategy|Counsel|Treasurer|Head|MD|EVP|SVP|VP))"
    r"\s+(?P<body>(?:I|You|We|So|Yes|No|Can|Could|Would|What|How|Why|When|Where|And|But|Just|Maybe|Let|Given|On|In|As|To|Thank|Thanks)\b.*)$",
    re.IGNORECASE,
)


def _is_call_boilerplate_segment(text: str) -> bool:
    stripped = text.strip()
    return stripped in CALL_MARKERS or bool(ROLE_LINE_RE.match(stripped)) or bool(CALL_BOILERPLATE_RE.match(stripped))


def _split_inline_call_markers(text: str) -> List[str]:
    parts: List[str] = []
    pos = 0
    for match in INLINE_CALL_MARKER_RE.finditer(text):
        before = text[pos : match.start()].strip()
        if before:
            parts.append(before)
        parts.append(match.group(1))
        pos = match.end()
    tail = text[pos:].strip()
    if tail:
        parts.append(tail)
    return parts or [text.strip()]


def _split_inline_role(text: str) -> List[str]:
    match = INLINE_ROLE_RE.match(text.strip())
    if not match:
        return [text.strip()]
    return [match.group("header").strip(), match.group("body").strip()]


def _normalize_sentence_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _trim_span(text: str, start: int, end: int) -> Tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_transcript_segments(text: str) -> List[str]:
    segments: List[str] = []
    current: List[str] = []

    def flush_current() -> None:
        if current:
            segments.append(" ".join(current).strip())
            current.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_current()
            continue

        pieces = _split_inline_call_markers(line)
        for piece in pieces:
            if piece in CALL_MARKERS:
                flush_current()
                segments.append(piece)
                continue
            
            role_parts = _split_inline_role(piece)
            if len(role_parts) == 2:
                flush_current()
                segments.append(role_parts[0])
                current.append(role_parts[1])
                continue

            if ROLE_LINE_RE.match(piece):
                flush_current()
                segments.append(piece)
                continue
            
            current.append(piece)

    flush_current()
    return [segment for segment in segments if segment]


def _split_inline_call_marker_spans(text: str, start: int, end: int) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    pos = start
    for match in INLINE_CALL_MARKER_RE.finditer(text, start, end):
        before_start, before_end = _trim_span(text, pos, match.start())
        if before_start < before_end:
            spans.append((before_start, before_end))
        marker_start, marker_end = _trim_span(text, match.start(), match.end())
        spans.append((marker_start, marker_end))
        pos = match.end()
    tail_start, tail_end = _trim_span(text, pos, end)
    if tail_start < tail_end:
        spans.append((tail_start, tail_end))
    return spans or [_trim_span(text, start, end)]


def _split_inline_role_span(text: str, start: int, end: int) -> List[Tuple[int, int]]:
    start, end = _trim_span(text, start, end)
    segment = text[start:end]
    match = INLINE_ROLE_RE.match(segment)
    if not match:
        return [(start, end)]
    header = (start + match.start("header"), start + match.end("header"))
    body = (start + match.start("body"), start + match.end("body"))
    return [_trim_span(text, *header), _trim_span(text, *body)]


def _split_transcript_segment_spans(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    current_start: int | None = None
    current_end: int | None = None

    def flush_current() -> None:
        nonlocal current_start, current_end
        if current_start is not None and current_end is not None:
            start, end = _trim_span(text, current_start, current_end)
            if start < end:
                spans.append((start, end))
        current_start = None
        current_end = None

    line_start = 0
    for raw_line in text.splitlines(keepends=True):
        line_end = line_start + len(raw_line)
        content_end = line_end - len(raw_line[len(raw_line.rstrip("\r\n")) :])
        start, end = _trim_span(text, line_start, content_end)

        if start >= end:
            flush_current()
            line_start = line_end
            continue

        for piece_start, piece_end in _split_inline_call_marker_spans(text, start, end):
            piece = text[piece_start:piece_end]
            if piece in CALL_MARKERS:
                flush_current()
                spans.append((piece_start, piece_end))
                continue

            role_spans = _split_inline_role_span(text, piece_start, piece_end)
            if len(role_spans) == 2:
                flush_current()
                spans.append(role_spans[0])
                current_start, current_end = role_spans[1]
                continue

            if ROLE_LINE_RE.match(piece.strip()):
                flush_current()
                spans.append((piece_start, piece_end))
                continue

            if current_start is None:
                current_start = piece_start
            current_end = piece_end

        line_start = line_end

    flush_current()
    return spans


def preprocess_transcript(text: str, min_chars: int = 40) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sents = []

    def append_candidate(candidate: str) -> None:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if len(candidate) >= min_chars or _is_call_boilerplate_segment(candidate):
            sents.append(candidate)

    for p in _split_transcript_segments(text):
        for s in nltk.sent_tokenize(p):
            role_parts = _split_inline_role(s)
            for part in role_parts:
                append_candidate(part)
    return sents


def preprocess_transcript_with_offsets(text: str, min_chars: int = 40) -> pd.DataFrame:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    records = []

    def append_candidate(start: int, end: int) -> None:
        start, end = _trim_span(text, start, end)
        if start >= end:
            return
        original = text[start:end]
        sentence = _normalize_sentence_text(original)
        if len(sentence) >= min_chars or _is_call_boilerplate_segment(sentence):
            records.append({
                "sentence_id": len(records),
                "sentence_text": sentence,
                "original_text": original,
                "start_char": start,
                "end_char": end,
            })

    for segment_start, segment_end in _split_transcript_segment_spans(text):
        segment_text = _normalize_sentence_text(text[segment_start:segment_end])
        if _is_call_boilerplate_segment(segment_text):
            append_candidate(segment_start, segment_end)
            continue

        for sent_start, sent_end in nltk.tokenize.PunktSentenceTokenizer().span_tokenize(text[segment_start:segment_end]):
            abs_start = segment_start + sent_start
            abs_end = segment_start + sent_end
            for role_start, role_end in _split_inline_role_span(text, abs_start, abs_end):
                append_candidate(role_start, role_end)

    records = sorted(records, key=lambda item: item["start_char"])
    cursor = 0
    for record in records:
        record["prefix_text"] = text[cursor : record["start_char"]]
        cursor = record["end_char"]
    tail_text = text[cursor:]

    df = pd.DataFrame.from_records(
        records,
        columns=["sentence_id", "sentence_text", "original_text", "prefix_text", "start_char", "end_char"],
    )
    df.attrs["tail_text"] = tail_text
    return df



def build_inference_frame(sentences: List[str]) -> pd.DataFrame:
    regex_df = extract_regex_features(pd.Series(sentences))
    surf_df = extract_surface_features(pd.Series(sentences))
    base = pd.DataFrame({"sentence_id": list(range(len(sentences))), "sentence_text": sentences, "split": "inference", "label": None})
    return pd.concat([base, regex_df, surf_df], axis=1)



def load_model_bundle(cfg: Dict) -> Dict:
    return load_json(artifact_path(cfg, "best_model", "metadata.json"))



def predict_sentences(cfg: Dict, sentences: List[str]) -> pd.DataFrame:
    bundle = load_model_bundle(cfg)
    feat_df = build_inference_frame(sentences)
    emb = encode_sentences_from_config(cfg, sentences)

    if bundle["family"] == "ensemble":
        members = bundle["ensemble"]["topk_members"]
        probs = [predict_family_proba(cfg, family, feat_df, emb, texts=sentences) for family in members]
        raw_weights = np.asarray([max(float(bundle["ensemble"].get("weights", {}).get(family, 0.0)), 0.0) for family in members], dtype=float)
        if raw_weights.sum() <= 0:
            raw_weights = np.ones(len(members), dtype=float)
        boilerplate_proba = np.average(np.vstack(probs), axis=0, weights=raw_weights / raw_weights.sum())
    else:
        boilerplate_proba = predict_family_proba(cfg, bundle["family"], feat_df, emb, texts=sentences)
    
    threshold = float(bundle["threshold"])
    pred = (boilerplate_proba >= threshold).astype(int)
    out = feat_df[["sentence_id", "sentence_text"]].copy()
    out["boilerplate_proba"] = boilerplate_proba
    out["pred_label"] = [INT_TO_LABEL[int(v)] for v in pred]
    structural_mask = out["sentence_text"].map(_is_call_boilerplate_segment)
    out.loc[structural_mask, "boilerplate_proba"] = 1.0
    out.loc[structural_mask, "pred_label"] = "boilerplate"
    return out


def predict_transcript(cfg: Dict, text: str, min_chars: int | None = None) -> pd.DataFrame:
    min_chars = int(cfg["project"]["min_sentence_chars"] if min_chars is None else min_chars)
    sentence_spans = preprocess_transcript_with_offsets(text, min_chars=min_chars)
    result = predict_sentences(cfg, sentence_spans["sentence_text"].tolist())
    if not sentence_spans.empty:
        result = result.merge(
            sentence_spans[["sentence_id", "original_text", "prefix_text", "start_char", "end_char"]],
            on="sentence_id",
            how="left",
        )
        result.attrs["tail_text"] = sentence_spans.attrs.get("tail_text", "")
    return result
