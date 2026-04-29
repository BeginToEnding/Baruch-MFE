from __future__ import annotations

SENTIMENT_BUCKETS = {"very_bearish", "bearish", "neutral", "bullish", "very_bullish"}
GUIDANCE_DIRECTIONS = {"raised", "reaffirmed", "lowered", "mixed", "none"}

CONTROLLED_THEME_TAXONOMY = {
    "guidance", "demand", "margin", "pricing", "cost", "inventory", "market_share",
    "product_launch", "macro", "supply_chain", "buyback", "dividend", "capex", "mna",
    "restructuring", "layoffs", "regulation", "litigation", "compliance", "china",
    "ai", "cloud", "enterprise", "consumer", "credit", "deposit",
    "commercial_real_estate", "capital"
}

SOURCE_SECTIONS = {"prepared", "qa", "unknown"}
SOURCE_SPEAKERS = {
    "ceo", "cfo", "ir", "analyst_question", "executive_answer",
    "other_executive", "unknown"
}


def _clip_score(x) -> float:
    try:
        v = float(x)
    except Exception:
        v = 0.0
    return max(-1.0, min(1.0, v))


def _as_str_list(items) -> list[str]:
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for x in items:
        if isinstance(x, str):
            s = x.strip()
            if s and s not in out:
                out.append(s)
    return out


def _normalize_source_section(x: str) -> str:
    s = str(x or "unknown").strip().lower()
    return s if s in SOURCE_SECTIONS else "unknown"


def _normalize_source_speaker(x: str) -> str:
    s = str(x or "unknown").strip().lower()
    return s if s in SOURCE_SPEAKERS else "unknown"


def _default_event_item() -> dict:
    return {
        "label": "",
        "category": "other",
        "sentiment": 0.0,
        "source_section": "unknown",
        "source_speaker": "unknown",
        "evidence": "",
    }


def _default_guidance_item() -> dict:
    return {
        "line_item": "other",
        "direction": "none",
        "source_section": "unknown",
        "source_speaker": "unknown",
        "evidence": "",
    }


def _validate_event_items(items) -> list[dict]:
    out: list[dict] = []
    for x in items or []:
        if not isinstance(x, dict):
            continue
        item = {**_default_event_item(), **x}
        item["label"] = str(item.get("label", "")).strip()
        item["category"] = str(item.get("category", "other")).strip().lower() or "other"
        item["sentiment"] = _clip_score(item.get("sentiment", 0.0))
        item["source_section"] = _normalize_source_section(item.get("source_section", "unknown"))
        item["source_speaker"] = _normalize_source_speaker(item.get("source_speaker", "unknown"))
        item["evidence"] = str(item.get("evidence", "")).strip()
        if item["label"]:
            out.append(item)
    return out


def _validate_guidance_items(items) -> list[dict]:
    out: list[dict] = []
    for x in items or []:
        if not isinstance(x, dict):
            continue
        item = {**_default_guidance_item(), **x}
        item["line_item"] = str(item.get("line_item", "other")).strip().lower() or "other"
        direction = str(item.get("direction", "none")).strip().lower()
        item["direction"] = direction if direction in GUIDANCE_DIRECTIONS else "none"
        item["source_section"] = _normalize_source_section(item.get("source_section", "unknown"))
        item["source_speaker"] = _normalize_source_speaker(item.get("source_speaker", "unknown"))
        item["evidence"] = str(item.get("evidence", "")).strip()
        out.append(item)
    return out


def validate_call_level(obj: dict) -> dict:
    obj = obj or {}
    bucket = str(obj.get("sentiment_bucket", "neutral")).strip().lower()
    if bucket not in SENTIMENT_BUCKETS:
        bucket = "neutral"

    themes: list[str] = []
    for t in _as_str_list(obj.get("themes", [])):
        tl = t.strip().lower()
        if tl and tl not in themes:
            themes.append(tl)

    return {
        "overall_sentiment_score": _clip_score(obj.get("overall_sentiment_score", 0.0)),
        "sentiment_bucket": bucket,
        "wins": _validate_event_items(obj.get("wins", [])),
        "risks": _validate_event_items(obj.get("risks", [])),
        "guidance": _validate_guidance_items(obj.get("guidance", [])),
        "themes": themes,
    }


def validate_speaker_level(obj: dict) -> dict:
    obj = obj or {}
    return {
        "ceo_sentiment_score": _clip_score(obj.get("ceo_sentiment_score", 0.0)),
        "cfo_sentiment_score": _clip_score(obj.get("cfo_sentiment_score", 0.0)),
        "analyst_sentiment_score": _clip_score(obj.get("analyst_sentiment_score", 0.0)),
        "prepared_sentiment_score": _clip_score(obj.get("prepared_sentiment_score", 0.0)),
        "qa_sentiment_score": _clip_score(obj.get("qa_sentiment_score", 0.0)),
        "reactive_sentiment_score": _clip_score(obj.get("reactive_sentiment_score", 0.0)),
    }


def validate_reactive_level(obj: dict) -> dict:
    obj = obj or {}
    proactive_topics = [s.strip().lower() for s in _as_str_list(obj.get("proactive_topics", []))]
    reactive_topics = [s.strip().lower() for s in _as_str_list(obj.get("reactive_topics", []))]
    proactive_set = set(proactive_topics)
    reactive_topics = [t for t in reactive_topics if t not in proactive_set]
    return {
        "proactive_topics": proactive_topics,
        "reactive_topics": reactive_topics,
    }


def validate_unified(obj: dict) -> dict:
    obj = obj or {}
    return {
        "call_level": validate_call_level(obj.get("call_level", {})),
        "speaker_level": validate_speaker_level(obj.get("speaker_level", {})),
        "reactive_level": validate_reactive_level(obj.get("reactive_level", {})),
    }
