# BP Classifier Project

A configurable end-to-end project for the **Boilerplate vs. Substantive Sentence Classifier** assignment.

This scaffold covers sentence extraction from earnings-call transcripts, multi-judge gold-label creation, 7 classifier families, out-of-fold threshold tuning under a substantive-recall constraint, held-out evaluation, and a Streamlit GUI for inline tagging.

## Judge design
Default code path is configured for:
- OpenAI
- Anthropic
- Ollama (`qwen3:4b`)

The Ollama helper is model-agnostic; swapping to `gemma3:4b` only requires a config change.

## Project layout

```text
bp_classifier_project/
├─ main.py
├─ config.yaml
├─ requirements.txt
├─ README.md
├─ .env.example
├─ data/
│  ├─ raw_transcripts/
│  ├─ interim/
│  └─ cache/
├─ artifacts/
│  ├─ models/
│  ├─ best_model/
│  └─ figures/
├─ outputs/
└─ src/
    ├─ data.py
    ├─ rubric.py
    ├─ labeling.py
    ├─ features.py
    ├─ models.py
    ├─ thresholding.py
    ├─ evaluate.py
    ├─ inference.py
    ├─ gui_app.py
    └─ utils.py
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run once for NLTK tokenizer data:

```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

## Environment variables
Copy `.env.example` to `.env` and fill the keys you plan to use.

## Pipeline Stages

Run any stage with:

```bash
python main.py --stage <stage_name>
# Windows:
.\venv\Scripts\python.exe main.py --stage <stage_name>
```

---

### `extract`
Reads every `.txt` file in `data/raw_transcripts/` and builds the sentence pool (`data/interim/all_sentences.parquet`). The extractor is transcript-aware: `Question`, `Answer`, `Operator`, `Analysts - …`, and `Executives - …` lines are split away from Q&A body text. Rerun everything downstream from `sample_gold` if sentence logic changes.

### `sample_gold`
Stratified-samples `labeling.gold_sample_size` rows from the sentence pool using `project.random_seed` → `data/interim/gold_candidates.parquet`. If `extract` output changes this sample may change too.

### `label_gold`
Runs the enabled judges in `config.yaml` (OpenAI, Anthropic, Ollama) and writes raw judge responses to `data/interim/judge_outputs.parquet` and `data/interim/judge_manifest.json`. This stage calls paid APIs. Rubric changes require rerunning if you want labels to reflect the new rubric.

### `audit_sample`
Builds the human-audit file `data/interim/audit_sample.csv`. Fill `audit_override_label` only where you want to override the majority-vote label. The file embeds `audit_judge_signature`; if `require_current_audit_signature: true` is set, stale overrides are ignored by `finalize_gold`.

### `audit_openai_anthropic_disagreements` *(optional shortcut)*
Produces a focused helper view (`data/interim/audit_sample_openai_anthropic_disagreements.csv`) containing only the OpenAI/Anthropic disagreements that are already in `audit_sample.csv`. It is a subset of the full audit — it does not create a new sample.

**This stage and the matching `merge` stage are optional.** They exist to reduce the manual review burden: instead of reading all 2,500 rows in `audit_sample.csv`, you only need to review the smaller disagreement subset. If you have the time and prefer to audit everything yourself, simply fill `audit_override_label` directly in `audit_sample.csv` and skip both stages entirely.

### `merge_openai_anthropic_disagreements` *(optional shortcut)*
Drops rows from the OpenAI/Anthropic helper CSV that are no longer in `audit_sample.csv`, then merges valid `audit_override_label` values back into `audit_sample.csv`. Close both CSV files in Excel/WPS before running — Windows locks open files.

**Skip this stage** if you chose to audit `audit_sample.csv` directly instead of using the disagreement shortcut.

### `finalize_gold`
Applies all audit overrides, computes final labels, and creates the stratified train/val/test split → `data/interim/gold_final.parquet`. Rerun all model stages downstream if audit labels change.

### `features`
Builds regex/surface features and sentence embeddings for `gold_final` → `data/interim/features_regex.parquet` and `data/cache/embeddings_all.npy`. Embedding provider and model are set in `config.yaml`. Rerun if `gold_final` changes.

### `grid_search`
Optional. Searches hyperparameters for lightweight model families and scores candidates under the substantive-recall constraint → `outputs/grid_search/best_hyperparams.json`. Set `training.use_grid_search_params: false` to ignore saved results.

### `tune_thresholds`
Builds 5-fold out-of-fold probabilities on the train+val pool and selects thresholds subject to `project.recall_floor_substantive` → `outputs/thresholds/best_thresholds.json` and `outputs/thresholds/oof_probabilities.parquet`. **This stage is slow** — transformer families retrain once per fold. Use `--family <name>` to tune a single model only; `--family ensemble` reuses saved OOF probabilities without retraining member models.

### `train_all`
Final refit of all configured families (except ensemble) on the combined train+val pool → `artifacts/models/*`. **FinBERT and SetFit are slow here.**

### `train_one`
Final refit for a single family on train+val. Requires `--family`, e.g.:
```bash
python main.py --stage train_one --family setfit
```
Use this after targeted code or hyperparameter changes to one model.

### `evaluate`
Evaluates all trained models on the held-out test split → `outputs/evaluation/leaderboard.csv`, `outputs/error_analysis/error_analysis_<family>.csv`, confusion matrices in `artifacts/figures`, and ensemble metadata. Rerun if thresholds or models change.

### `package_best`
Writes the selected best-model family and threshold to `artifacts/best_model/metadata.json` for inference packaging. The GUI reads this file.

---

### Compound shortcuts

`from_gold` — assumes `gold_final.parquet` already exists; runs `features → tune_thresholds → train_all → evaluate → package_best` in one command:
```bash
python main.py --stage from_gold
```

`from_models` — assumes trained models and thresholds already exist; runs `evaluate → package_best`:
```bash
python main.py --stage from_models
```

---

## Workflows

### Full pipeline (first run or after changing transcripts / labeling)

The labeling and audit stages require manual review in the middle, so they cannot be collapsed into a single command.

```bash
python main.py --stage extract
python main.py --stage sample_gold
python main.py --stage label_gold
python main.py --stage audit_sample

# Option A — audit only the GPT/Sonnet disagreements (lower workload):
python main.py --stage audit_openai_anthropic_disagreements
# manually fill audit_sample_openai_anthropic_disagreements.csv
python main.py --stage merge_openai_anthropic_disagreements

# Option B — audit everything directly (skip the two stages above):
# manually fill audit_override_label in audit_sample.csv

python main.py --stage finalize_gold
python main.py --stage from_gold      # features → train → evaluate → package
```

### Skip labeling and audit (gold labels already finalized)

Use this when `gold_final.parquet` is ready and you only need to (re)train or (re)tune:

```bash
python main.py --stage from_gold
```

Or run stages individually if you want finer control:

```bash
python main.py --stage features
python main.py --stage tune_thresholds          # slow — all families
python main.py --stage tune_thresholds --family finbert   # single family
python main.py --stage train_all                # slow — FinBERT / SetFit
python main.py --stage train_one --family setfit
python main.py --stage evaluate
python main.py --stage package_best
```

### Use pre-trained models as-is (no retraining or threshold tuning)

If models are already trained and thresholds are set, just select the best model and launch the GUI:

```bash
python main.py --stage from_models   # evaluate → package_best
streamlit run src/gui_app.py
```

---

## Time budget

`tune_thresholds` and `train_all` are the most time-consuming stages — transformer families (FinBERT, SetFit) train once per fold during threshold tuning and again during final refit. On a CPU-only machine expect tens of minutes per transformer family. Use `--family <name>` with `tune_thresholds` and `train_one` to iterate on a single model without rerunning the rest.

## Walkthrough notebook

`walkthrough.ipynb` displays all pipeline artifacts without rerunning any stage. Open it after a run to inspect the sentence pool, judge outputs, gold-label distribution, feature prevalence, threshold-search curves, the leaderboard, per-family confusion matrices, and error-analysis examples. It also includes a class-balance chart and a training-time summary.

```bash
jupyter notebook walkthrough.ipynb
```

## GUI

```bash
streamlit run src/gui_app.py
```

Upload a `.txt` transcript or paste text, then click **Run**. Boilerplate sentences are highlighted in red; hover any sentence to see its predicted probability.

## Notes
- FinBERT and SetFit are implemented behind optional dependencies; adjust hyperparameters for your machine as needed.
- FastText is optional and will be skipped if the package is unavailable.
- Intermediate outputs are written to Parquet to support resume-on-interruption.
- Thresholding uses pooled out-of-fold probabilities instead of a single validation split.
