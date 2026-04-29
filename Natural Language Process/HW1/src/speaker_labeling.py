from __future__ import annotations

def normalize_role(raw_role: str) -> str:
    if not raw_role:
        return "unknown"
    s = raw_role.lower()
    if "operator" in s:
        return "operator"
    if "analyst" in s:
        return "analyst"
    if "chief executive officer" in s or "ceo" in s or "chair, president & ceo" in s:
        return "ceo"
    if "chief financial officer" in s or "cfo" in s or "treasurer" in s:
        return "cfo"
    if "investor relations" in s or "ir" in s:
        return "ir"
    if "executive" in s or "president" in s or "vice president" in s:
        return "executive_other"
    return "other"

def add_speaker_labels(record: dict) -> dict:
    for b in record.get("prepared_blocks", []):
        b["speaker_group"] = normalize_role(b.get("role", ""))
    for pair in record.get("qa_pairs", []):
        pair["q_speaker_group"] = normalize_role(pair.get("q_role", ""))
        pair["a_speaker_group"] = normalize_role(pair.get("a_role", ""))
    return record
