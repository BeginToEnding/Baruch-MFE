from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.price_loader import PriceLoader
from src.utils import read_json


GUIDANCE_SCORE_MAP = {
    "raised": 1.0,
    "reaffirmed": 0.0,
    "lowered": -1.0,
    "mixed": 0.0,
}


EXTERNAL_SIGNAL_COLS = [
    "ext_mean_return_5d",
    "ext_macd",
    "ext_volume_adv20",
]


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _avg(values: List[float], default: float = 0.0) -> float:
    if not values:
        return default
    return float(np.mean(values))


def _normalize_theme_list(themes: List[str]) -> set[str]:
    out = set()
    for t in themes or []:
        if not t:
            continue
        t_norm = str(t).strip().lower()
        if t_norm:
            out.add(t_norm)
    return out


def _extract_risk_categories(risks: List[Dict]) -> set[str]:
    cats = set()
    for r in risks or []:
        cat = str(r.get("category", "")).strip().lower()
        if cat:
            cats.add(cat)
    return cats


def _guidance_net_score(guidance_items: List[Dict]) -> float:
    vals = []
    for g in guidance_items or []:
        direction = str(g.get("direction", "")).strip().lower()
        if direction in GUIDANCE_SCORE_MAP:
            vals.append(GUIDANCE_SCORE_MAP[direction])
    return _avg(vals, default=0.0)


def _reactive_topic_ratio(proactive_topics: List[str], reactive_topics: List[str]) -> float:
    proactive = {str(x).strip().lower() for x in (proactive_topics or []) if str(x).strip()}
    reactive = {str(x).strip().lower() for x in (reactive_topics or []) if str(x).strip()}
    all_topics = proactive | reactive
    return len(reactive) / max(len(all_topics), 1)


def _avg_event_sentiment(items: List[Dict]) -> float:
    vals = [_safe_float(x.get("sentiment"), 0.0) for x in (items or [])]
    return _avg(vals, default=0.0)


def _build_external_signal_frame(
    tickers: list[str],
    prices_dir: str | Path,
    price_cfg: dict,
) -> pd.DataFrame:
    loader = PriceLoader(
        prices_dir=prices_dir,
        start_date=price_cfg.get("start_date", "2023-09-01"),
    )

    frames = []
    for ticker in sorted(set(tickers)):
        px = loader.get_or_fetch_prices(ticker).copy()
        if px.empty:
            continue

        px = px.sort_values("Date").reset_index(drop=True)
        px["Date"] = pd.to_datetime(px["Date"]).astype("datetime64[ns]")
        px["daily_return"] = px["Close"].pct_change()
        px["ext_mean_return_5d"] = px["daily_return"].rolling(5).mean()

        ema12 = px["Close"].ewm(span=12, adjust=False).mean()
        ema26 = px["Close"].ewm(span=26, adjust=False).mean()
        px["ext_macd"] = (ema12 - ema26) / ema26.replace(0.0, np.nan)

        adv20 = px["Volume"].rolling(20).mean()
        px["ext_volume_adv20"] = px["Volume"] / adv20.replace(0.0, np.nan)

        keep_cols = ["Date"] + EXTERNAL_SIGNAL_COLS
        tmp = px[keep_cols].copy()
        tmp["ticker"] = ticker
        frames.append(tmp)

    if not frames:
        return pd.DataFrame(columns=["ticker", "Date"] + EXTERNAL_SIGNAL_COLS)

    out = pd.concat(frames, ignore_index=True)
    out["Date"] = pd.to_datetime(out["Date"]).astype("datetime64[ns]")
    return out


def _add_external_signals(
    df: pd.DataFrame,
    prices_dir: str | Path,
    price_cfg: dict,
) -> pd.DataFrame:
    signal_df = _build_external_signal_frame(df["ticker"].tolist(), prices_dir, price_cfg)
    if signal_df.empty:
        out = df.copy()
        for col in EXTERNAL_SIGNAL_COLS:
            out[col] = np.nan
        return out

    base_df = df.copy()
    base_df["call_date"] = pd.to_datetime(base_df["call_date"]).astype("datetime64[ns]")
    signal_df["Date"] = pd.to_datetime(signal_df["Date"]).astype("datetime64[ns]")

    merged_parts = []
    for ticker, g in base_df.groupby("ticker", sort=False):
        ticker_signals = signal_df.loc[signal_df["ticker"] == ticker].sort_values("Date").copy()
        ticker_calls = g.sort_values("call_date").copy()

        merged = pd.merge_asof(
            ticker_calls,
            ticker_signals,
            left_on="call_date",
            right_on="Date",
            direction="backward",
        )
        merged = merged.drop(columns=["Date", "ticker_y"], errors="ignore")
        merged = merged.rename(columns={"ticker_x": "ticker"})
        merged_parts.append(merged)

    return pd.concat(merged_parts, ignore_index=True)


def build_features(
    extraction_json_dir: str | Path,
    prices_dir: str | Path | None = None,
    price_cfg: dict | None = None,
    feature_cfg: dict | None = None,
) -> pd.DataFrame:
    extraction_json_dir = Path(extraction_json_dir)
    files = sorted(extraction_json_dir.glob("*.json"))
    feature_cfg = feature_cfg or {}
    use_external_signals = bool(feature_cfg.get("use_external_signals", False))

    raw_rows = []

    for fp in files:
        obj = read_json(fp)

        meta = obj.get("_meta", {})
        call_level = obj.get("call_level", {})
        speaker_level = obj.get("speaker_level", {})
        reactive_level = obj.get("reactive_level", {})

        ticker = (meta.get("ticker", "") or "").replace("\ufeff", "").strip()
        quarter = (meta.get("quarter", "") or "").replace("\ufeff", "").strip()
        call_date = pd.to_datetime(meta.get("call_date"))

        overall_sentiment_score = _safe_float(call_level.get("overall_sentiment_score"), 0.0)
        ceo_sent = _safe_float(speaker_level.get("ceo_sentiment_score"), 0.0)
        cfo_sent = _safe_float(speaker_level.get("cfo_sentiment_score"), 0.0)
        analyst_sent = _safe_float(speaker_level.get("analyst_sentiment_score"), 0.0)
        reactive_sent = _safe_float(speaker_level.get("reactive_sentiment_score"), 0.0)

        ceo_cfo_consistency = abs(ceo_sent - cfo_sent)

        risks = call_level.get("risks", []) or []
        guidance = call_level.get("guidance", []) or []
        themes = _normalize_theme_list(call_level.get("themes", []) or [])

        proactive_topics = reactive_level.get("proactive_topics", []) or []
        reactive_topics = reactive_level.get("reactive_topics", []) or []

        guidance_net_score = _guidance_net_score(guidance)
        reactive_topic_ratio = _reactive_topic_ratio(proactive_topics, reactive_topics)
        avg_risk_sentiment = _avg_event_sentiment(risks)
        risk_categories = _extract_risk_categories(risks)

        raw_rows.append(
            {
                "ticker": ticker,
                "quarter": quarter,
                "call_date": call_date,
                "overall_sentiment_score": overall_sentiment_score,
                "ceo_cfo_consistency": ceo_cfo_consistency,
                "analyst_sentiment_score": analyst_sent,
                "reactive_sentiment_score": reactive_sent,
                "guidance_net_score": guidance_net_score,
                "reactive_topic_ratio": reactive_topic_ratio,
                "avg_risk_sentiment": avg_risk_sentiment,
                "_risk_categories": risk_categories,
                "_themes": themes,
            }
        )

    base_cols = [
        "ticker",
        "quarter",
        "call_date",
        "overall_sentiment_score",
        "ceo_cfo_consistency",
        "analyst_sentiment_score",
        "reactive_sentiment_score",
        "guidance_net_score",
        "reactive_topic_ratio",
        "avg_risk_sentiment",
        "risk_persistence_ratio",
        "new_risk_flag",
        "sentiment_delta",
        "guidance_delta",
        "new_theme_ratio",
    ]
    if use_external_signals:
        base_cols += EXTERNAL_SIGNAL_COLS

    if not raw_rows:
        return pd.DataFrame(columns=base_cols)

    df = pd.DataFrame(raw_rows)
    df = df.sort_values(["ticker", "call_date"]).reset_index(drop=True)

    group = df.groupby("ticker")
    df["sentiment_delta"] = group["overall_sentiment_score"].diff().fillna(0.0)
    df["guidance_delta"] = group["guidance_net_score"].diff().fillna(0.0)

    df["_prev_risk_categories"] = group["_risk_categories"].shift(1)
    df["_prev_themes"] = group["_themes"].shift(1)

    def _risk_persistence(cur_prev):
        cur, prev = cur_prev
        if not isinstance(prev, set):
            return 0.0
        return len(cur & prev) / max(len(prev), 1)

    def _new_risk_flag(cur_prev):
        cur, prev = cur_prev
        if not isinstance(prev, set):
            return 0
        return int(len(cur - prev) > 0)

    def _new_theme_ratio(cur_prev):
        cur, prev = cur_prev
        if not isinstance(prev, set):
            return 0.0
        return len(cur - prev) / max(len(cur), 1)

    df["risk_persistence_ratio"] = list(
        map(_risk_persistence, zip(df["_risk_categories"], df["_prev_risk_categories"]))
    )
    df["new_risk_flag"] = list(
        map(_new_risk_flag, zip(df["_risk_categories"], df["_prev_risk_categories"]))
    )
    df["new_theme_ratio"] = list(
        map(_new_theme_ratio, zip(df["_themes"], df["_prev_themes"]))
    )

    df = df.drop(columns=["_prev_risk_categories", "_prev_themes"])

    if use_external_signals:
        if prices_dir is None or price_cfg is None:
            raise ValueError("prices_dir and price_cfg are required when use_external_signals=True")
        df = _add_external_signals(df, prices_dir=prices_dir, price_cfg=price_cfg)

    return df[base_cols].copy()
