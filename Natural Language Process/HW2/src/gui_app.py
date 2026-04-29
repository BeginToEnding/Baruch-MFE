from pathlib import Path
import sys
import html

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

from inference import predict_transcript
from utils import load_config


CFG = load_config("config.yaml")
RESULT_SCHEMA_VERSION = 2


def _global_style() -> str:
    return """
    <style>
      .stApp {
        background: #080d19;
        color: #edf2ff;
      }
      [data-testid="stHeader"] {
        background: rgba(8, 13, 25, 0.86);
      }
      .app-shell {
        max-width: 1220px;
        margin: 0 auto;
      }
      .hero {
        border-bottom: 1px solid #243149;
        padding: 18px 0 12px;
        margin-bottom: 10px;
      }
      .brand-row {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .brand-icon {
        width: 34px;
        height: 34px;
        border-radius: 8px;
        display: grid;
        place-items: center;
        background: #ff9f58;
        color: #111827;
        font-weight: 800;
      }
      .brand-title {
        font-size: 22px;
        font-weight: 750;
        letter-spacing: 0;
        color: #ffffff;
      }
      .brand-subtitle {
        color: #e3ebfb;
        font-size: 12px;
        margin-top: 2px;
      }
      .stMarkdown, .stText, .stCaption, label, [data-testid="stWidgetLabel"], p {
        color: #f7faff !important;
      }
      /* File uploader — cover the entire widget including the post-upload file-info row */
      [data-testid="stFileUploader"],
      [data-testid="stFileUploader"] > div,
      [data-testid="stFileUploader"] section {
        background: #182236 !important;
        border-color: #5f7190 !important;
      }
      [data-testid="stFileUploader"] section {
        border: 1px solid #5f7190 !important;
      }
      [data-testid="stFileUploader"] * {
        color: #ffffff !important;
        opacity: 1 !important;
        background: transparent !important;
      }
      /* Restore "Browse files" button */
      [data-testid="stFileUploader"] button {
        background: #ffffff !important;
        color: #111827 !important;
        border: 1px solid #cbd5e1 !important;
        opacity: 1 !important;
      }
      [data-testid="stFileUploader"] button * {
        color: #111827 !important;
        background: transparent !important;
      }
      [data-testid="stDownloadButton"] button {
        background: #1b3a5c !important;
        color: #e8f0ff !important;
        border: 1px solid #3d6b9e !important;
      }
      [data-testid="stDownloadButton"] button:hover {
        background: #274e7a !important;
        color: #ffffff !important;
      }
      [data-testid="stDownloadButton"] button * {
        color: inherit !important;
      }
      /* All regular (secondary) buttons → dark style */
      [data-testid="stButton"] button {
        background: #1b2b45 !important;
        color: #d8e8ff !important;
        border: 1px solid #3d5a80 !important;
      }
      [data-testid="stButton"] button:hover {
        background: #253d5f !important;
        color: #ffffff !important;
        border-color: #5a8ac0 !important;
      }
      /* Primary button (Run) → restore Streamlit red accent */
      [data-testid="stButton"] button[data-testid="baseButton-primary"],
      [data-testid="baseButton-primary"] {
        background: #ff4b4b !important;
        color: #ffffff !important;
        border: none !important;
      }
      [data-testid="stButton"] button[data-testid="baseButton-primary"]:hover,
      [data-testid="baseButton-primary"]:hover {
        background: #e03a3a !important;
        color: #ffffff !important;
      }
      /* Fallback for older Streamlit selector */
      [data-testid="baseButton-secondary"] {
        background: #1b2b45 !important;
        color: #d8e8ff !important;
        border: 1px solid #3d5a80 !important;
      }
      [data-testid="baseButton-secondary"]:hover {
        background: #253d5f !important;
        color: #ffffff !important;
        border-color: #5a8ac0 !important;
      }
      [data-testid="stStatusWidget"],
      [data-testid="stStatusWidget"] *,
      header button,
      header span,
      header p {
        color: #c8d8f0 !important;
        opacity: 1 !important;
      }
      .viewer::-webkit-scrollbar {
        width: 8px;
      }
      .viewer::-webkit-scrollbar-track {
        background: #0a1628;
      }
      .viewer::-webkit-scrollbar-thumb {
        background: #5a8fc0;
        border-radius: 4px;
      }
      .viewer::-webkit-scrollbar-thumb:hover {
        background: #7ab0e0;
      }
      textarea {
        background: #0f172a !important;
        color: #ffffff !important;
        border: 1px solid #64748b !important;
      }
      textarea::placeholder {
        color: #d6e0f0 !important;
      }
      [data-testid="stAlert"] {
        background: #172842;
        color: #ffffff;
      }
      .viewer {
        height: calc(100vh - 260px);
        min-height: 520px;
        overflow-y: auto;
        border-left: 1px solid #1b2639;
        border-right: 1px solid #1b2639;
        background: #0b1020;
        padding: 28px 42px 56px;
        box-shadow: inset 0 16px 50px rgba(0,0,0,0.22);
      }
      .doc-flow {
        max-width: 780px;
        margin: 0 auto;
        color: #f4f7ff;
        font-size: 15px;
        line-height: 1.78;
        overflow-wrap: break-word;
      }
      .bp-sentence {
        position: relative;
        border-radius: 4px;
        padding: 1px 2px 2px;
        outline: 1px solid transparent;
        box-decoration-break: clone;
        -webkit-box-decoration-break: clone;
        transition: background 120ms ease, outline-color 120ms ease;
      }
      .bp-sentence.boilerplate {
        color: #fff3f6;
        background: rgba(170, 53, 83, 0.72);
        border: 1px solid rgba(255, 157, 181, 0.28);
      }
      .bp-sentence.substantive {
        color: #f4f7ff;
      }
      .bp-sentence:hover {
        outline-color: #9bbcff;
        background: rgba(82, 119, 255, 0.18);
      }
      .bp-sentence.boilerplate:hover {
        background: rgba(190, 62, 94, 0.82);
      }
      .bp-sentence:hover::after {
        content: attr(data-proba);
        position: absolute;
        left: 0;
        bottom: calc(100% + 6px);
        z-index: 10;
        white-space: nowrap;
        color: #f8fbff;
        background: #111827;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 4px 7px;
        font-size: 12px;
        line-height: 1;
        box-shadow: 0 8px 22px rgba(0,0,0,0.32);
      }
      .legend-bar {
        display: grid;
        grid-template-columns: 1fr 1fr;
        height: 4px;
        margin: 8px 0 0;
      }
      .legend-bar div:first-child {
        background: #ff4d7d;
      }
      .legend-bar div:last-child {
        background: #39d98a;
      }
    </style>
    """


def _render_tagged_transcript(result) -> str:
    chunks = []

    for _, row in result.sort_values("sentence_id").iterrows():
        is_boilerplate = row["pred_label"] == "boilerplate"
        proba = float(row["boilerplate_proba"])
        if "original_text" not in row or "prefix_text" not in row:
            continue
        chunks.append(html.escape(str(row.get("prefix_text", ""))).replace("\n", "<br>"))

        original_sentence = html.escape(str(row.get("original_text", "")))
        css_class = "bp-sentence boilerplate" if is_boilerplate else "bp-sentence substantive"
        chunks.append(
            f'<span class="{css_class}" data-proba="p(boilerplate)={proba:.3f}">{original_sentence}</span>'
        )

    chunks.append(html.escape(str(result.attrs.get("tail_text", ""))).replace("\n", "<br>"))

    highlighted_text = "".join(chunks)

    return f"""
    <div class="viewer"><div class="doc-flow">
      {highlighted_text}
    </div>
    </div>
    """


st.set_page_config(page_title=CFG["gui"]["page_title"], layout=CFG["gui"]["page_layout"])
st.markdown(_global_style(), unsafe_allow_html=True)
st.markdown(
    """
    <div class="app-shell">
      <div class="hero">
        <div class="brand-row">
          <div class="brand-icon">B</div>
          <div>
            <div class="brand-title">Boilerplate Detector</div>
            <div class="brand-subtitle">Highlights scripted intros, safe-harbor language, speaker titles, and operator chatter in earnings-call transcripts.</div>
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "transcript_text" not in st.session_state:
    st.session_state["transcript_text"] = ""
if "source_name" not in st.session_state:
    st.session_state["source_name"] = "Pasted text"
if st.session_state.get("result_schema_version") != RESULT_SCHEMA_VERSION:
    st.session_state.pop("result", None)
    st.session_state.pop("result_text", None)
    st.session_state["result_schema_version"] = RESULT_SCHEMA_VERSION

with st.container():
    col_file, col_run, col_clear = st.columns([4.2, 1.2, 1.2], vertical_alignment="bottom")
    with col_file:
        uploaded = st.file_uploader("Transcript", type=["txt"])
    with col_run:
        run = st.button("Run", type="primary", use_container_width=True)
    with col_clear:
        clear = st.button("Clear", use_container_width=True)

if clear:
    st.session_state.pop("result", None)
    st.session_state.pop("result_text", None)
    st.session_state.pop("upload_id", None)
    st.session_state["transcript_text"] = ""
    st.session_state["source_name"] = "Pasted text"

if uploaded is not None:
    upload_id = f"{uploaded.name}:{uploaded.size}"
    if st.session_state.get("upload_id") != upload_id:
        st.session_state["upload_id"] = upload_id
        st.session_state.pop("result", None)
        st.session_state.pop("result_text", None)
        st.session_state["transcript_text"] = uploaded.getvalue().decode("utf-8", errors="ignore")
        st.session_state["source_name"] = uploaded.name

text = st.text_area(
    "Transcript text",
    key="transcript_text",
    height=180,
    placeholder="Upload a .txt transcript or paste text here...",
)
text = text.replace("\r\n", "\n").replace("\r", "\n")
source_name = st.session_state.get("source_name", "Pasted text")
if uploaded is None and text.strip():
    source_name = "Pasted text"
    st.session_state["source_name"] = source_name

if run and text.strip():
    result = predict_transcript(CFG, text, min_chars=1)
    st.session_state["result"] = result
    st.session_state["result_text"] = text
    st.session_state["result_schema_version"] = RESULT_SCHEMA_VERSION
    st.session_state["source_name"] = source_name

if "result" in st.session_state:
    result = st.session_state["result"]
    source_name = st.session_state.get("source_name", "Pasted text")
    boilerplate_count = int((result["pred_label"] == "boilerplate").sum())
    substantive_count = int((result["pred_label"] == "substantive").sum())
    total = max(len(result), 1)

    c0, c1, c2, c3 = st.columns([2.2, 1, 1, 1], vertical_alignment="center")
    c0.markdown(f"**{html.escape(source_name)}**")
    c1.metric("Total", int(total))
    c2.metric("Boilerplate", f"{boilerplate_count}", f"{100 * boilerplate_count / total:.1f}%")
    c3.metric("Substantive", f"{substantive_count}", f"{100 * substantive_count / total:.1f}%")
    st.markdown('<div class="legend-bar"><div></div><div></div></div>', unsafe_allow_html=True)

    st.markdown(_render_tagged_transcript(result), unsafe_allow_html=True)

    st.download_button(
        "Download predictions CSV",
        result.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{Path(source_name).stem}_predictions.csv" if source_name != "Pasted text" else "predictions.csv",
        mime="text/csv",
    )
elif run:
    st.warning("Upload a .txt file or paste transcript text first.")
else:
    st.info("Upload a transcript or paste text, then run the detector.")
