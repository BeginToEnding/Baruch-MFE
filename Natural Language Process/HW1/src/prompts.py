from __future__ import annotations
from typing import List, Dict
from src.transcript_parser import transcript_to_prompt_text


def _few_shot_messages(prompt_cfg: dict) -> List[Dict]:
    return prompt_cfg.get("few_shot", {}).get("unified", [])


FIELD_DEFINITIONS_TEXT = """
Field definitions:
- overall_sentiment_score: sentiment for the entire earnings call transcript, in [-1, 1].
- sentiment_bucket: one of very_bearish, bearish, neutral, bullish, very_bullish.
- wins: top 3-5 concrete positive events grounded in the transcript.
- risks: top 3-5 concrete negative events grounded in the transcript.
- For each win and risk, output a sentiment score in [-1, 1] measuring the strength and tone of that event only.
  Positive wins should usually have positive sentiment; more emphatic or clearly positive wins should have larger positive values.
  Negative risks should usually have negative sentiment; more severe or clearly negative risks should have smaller values closer to -1.
- guidance: explicit forward-looking statements about revenue, EPS, margin, segment outlook, cost, volume, demand, capital return, or other management outlook.
- themes: main call themes as a short list of labels. Prefer the controlled taxonomy, but if a clearly important theme falls outside it, add a concise new theme label.
- ceo_sentiment_score: sentiment from CEO remarks only.
- cfo_sentiment_score: sentiment from CFO remarks only.
- analyst_sentiment_score: sentiment from analyst questions only.
- prepared_sentiment_score: sentiment from all content before Q&A begins, combining IR and all executives before Q&A.
- qa_sentiment_score: sentiment from the full Q&A section, combining both questions and answers.
- reactive_sentiment_score: sentiment only for the subset of Q&A discussion tied to topics that were not mentioned in prepared remarks and first appeared in Q&A. This should reflect both analyst concern and the quality, confidence, and credibility of management responses on those reactive topics.
- proactive_topics: major topics proactively mentioned in prepared remarks.
- reactive_topics: topics discussed in Q&A that were not mentioned in prepared remarks. They may be derived from or expand beyond the controlled themes when necessary.
""".strip()


WIN_RISK_GUIDANCE_TEXT = """
Wins should be top 3-5 concrete positive events. Examples include new customer, record revenue,
margin expansion, successful product ramp, share buyback, guidance raise, market-share gain,
product launch, cost savings, strong bookings, large deployment, regulatory approval.

Risks should be top 3-5 concrete negative events. Examples include softening demand, inventory build,
margin compression, litigation, regulatory exposure, lowered guidance, customer concentration,
macro headwinds, supply constraints, pricing pressure, weaker consumer demand, credit deterioration.

Guidance should capture any explicit management outlook. Direction must be one of:
raised, reaffirmed, lowered, mixed, none.
""".strip()


THEME_TAXONOMY_TEXT = """
Controlled theme taxonomy:
- guidance
- demand
- margin
- pricing
- cost
- inventory
- market_share
- product_launch
- macro
- supply_chain
- buyback
- dividend
- capex
- mna
- restructuring
- layoffs
- regulation
- litigation
- compliance
- china
- ai
- cloud
- enterprise
- consumer
- credit
- deposit
- commercial_real_estate
- capital

Use these controlled themes whenever they fit.
If an important topic clearly falls outside this taxonomy, you may include a short additional theme label.
""".strip()


SCHEMA_TEXT = r'''
Return valid JSON only and follow this schema exactly:
{
  "call_level": {
    "overall_sentiment_score": 0.35,
    "sentiment_bucket": "bullish",
    "wins": [
      {
        "label": "...",
        "category": "record_revenue",
        "sentiment": 0.82,
        "source_section": "prepared",
        "source_speaker": "ceo",
        "evidence": "..."
      }
    ],
    "risks": [
      {
        "label": "...",
        "category": "softening_demand",
        "sentiment": -0.63,
        "source_section": "qa",
        "source_speaker": "executive_answer",
        "evidence": "..."
      }
    ],
    "guidance": [
      {
        "line_item": "revenue",
        "direction": "raised",
        "source_section": "prepared",
        "source_speaker": "cfo",
        "evidence": "..."
      }
    ],
    "themes": ["ai", "guidance", "margin"]
  },
  "speaker_level": {
    "ceo_sentiment_score": 0.48,
    "cfo_sentiment_score": 0.21,
    "analyst_sentiment_score": -0.10,
    "prepared_sentiment_score": 0.42,
    "qa_sentiment_score": 0.18,
    "reactive_sentiment_score": -0.15
  },
  "reactive_level": {
    "proactive_topics": ["ai", "guidance", "margin"],
    "reactive_topics": ["supply_chain"]
  }
}
'''.strip()


def build_system_prompt(prompt_cfg: dict) -> str:
    base = str(prompt_cfg.get("system", "")).strip()
    static_rules = "\n\n".join([
        FIELD_DEFINITIONS_TEXT,
        WIN_RISK_GUIDANCE_TEXT,
        THEME_TAXONOMY_TEXT,
        SCHEMA_TEXT,
        "Rules:\n- Return JSON only.\n- Use transcript-grounded evidence only.\n- Keep labels short, concrete, and non-duplicative.\n- Use at most 5 wins and at most 5 risks.\n- source_section should be one of prepared or qa.\n- source_speaker should be one of ceo, cfo, ir, analyst_question, executive_answer, other_executive, unknown.\n- reactive_topics must exclude anything already present in proactive_topics.",
    ])
    return (base + "\n\n" + static_rules).strip() if base else static_rules


def build_unified_messages(record: dict, prompt_cfg: dict) -> List[Dict]:
    transcript = transcript_to_prompt_text(record)
    user_prompt = f'''
Extract structured information from this earnings call transcript.

Transcript metadata:
- ticker: {record.get("ticker", "")}
- quarter: {record.get("quarter", "")}
- call_date: {record.get("call_date", "")}

Transcript:
{transcript}
'''.strip()

    return [
        {"role": "system", "content": build_system_prompt(prompt_cfg)},
        *_few_shot_messages(prompt_cfg),
        {"role": "user", "content": user_prompt},
    ]
