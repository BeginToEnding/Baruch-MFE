from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import argparse

from bp_classifier.data import build_sentence_pool, sample_gold_candidates, finalize_gold_labels_and_splits
from bp_classifier.evaluate import evaluate_all_models, package_best_model
from bp_classifier.features import build_feature_cache
from bp_classifier.grid_search import run_hyperparameter_search
from bp_classifier.labeling import (
    build_audit_sample,
    build_openai_anthropic_disagreement_audit,
    merge_openai_anthropic_disagreement_audit,
    run_labeling_pipeline,
)
from bp_classifier.models import train_all_families, train_one_family
from bp_classifier.thresholding import tune_all_thresholds
from bp_classifier.utils import ensure_project_dirs, load_config, setup_logging

STAGES = [
    "extract",
    "sample_gold",
    "label_gold",
    "audit_sample",
    "audit_openai_anthropic_disagreements",
    "merge_openai_anthropic_disagreements",
    "finalize_gold",
    "features",
    "grid_search",
    "train_one",
    "train_all",
    "tune_thresholds",
    "evaluate",
    "package_best",
    # compound shortcuts
    "from_gold",    # features → tune_thresholds → train_all → evaluate → package_best
    "from_models",  # evaluate → package_best
]

_FROM_GOLD_STAGES = ["features", "tune_thresholds", "train_all", "evaluate", "package_best"]
_FROM_MODELS_STAGES = ["evaluate", "package_best"]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BP Classifier project entrypoint")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config")
    parser.add_argument("--stage", required=True, choices=STAGES)
    parser.add_argument("--family", help="Model family for --stage train_one")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    ensure_project_dirs(cfg)
    logger = setup_logging()

    def _run(stage: str) -> None:
        logger.info("Running stage: %s", stage)
        if stage == "extract":
            build_sentence_pool(cfg, logger)
        elif stage == "sample_gold":
            sample_gold_candidates(cfg, logger)
        elif stage == "label_gold":
            run_labeling_pipeline(cfg, logger)
        elif stage == "audit_sample":
            build_audit_sample(cfg, logger)
        elif stage == "audit_openai_anthropic_disagreements":
            build_openai_anthropic_disagreement_audit(cfg, logger)
        elif stage == "merge_openai_anthropic_disagreements":
            merge_openai_anthropic_disagreement_audit(cfg, logger)
        elif stage == "finalize_gold":
            finalize_gold_labels_and_splits(cfg, logger)
        elif stage == "features":
            build_feature_cache(cfg, logger)
        elif stage == "grid_search":
            run_hyperparameter_search(cfg, logger)
        elif stage == "train_one":
            if not args.family:
                raise ValueError("--family is required for --stage train_one")
            train_one_family(cfg, logger, args.family)
        elif stage == "train_all":
            train_all_families(cfg, logger)
        elif stage == "tune_thresholds":
            tune_all_thresholds(cfg, logger, family=args.family)
        elif stage == "evaluate":
            evaluate_all_models(cfg, logger)
        elif stage == "package_best":
            package_best_model(cfg, logger)
        else:
            raise ValueError(f"Unknown stage: {stage}")

    if args.stage == "from_gold":
        for stage in _FROM_GOLD_STAGES:
            _run(stage)
    elif args.stage == "from_models":
        for stage in _FROM_MODELS_STAGES:
            _run(stage)
    else:
        _run(args.stage)

if __name__ == "__main__":
    main()
