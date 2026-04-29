from __future__ import annotations

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from xgboost import XGBClassifier, XGBRegressor


REGRESSION_TARGETS = {"y_raw", "y_excess"}
CLASSIFICATION_TARGETS = {"y_class"}

REGRESSION_MODELS = {"ridge_reg", "rf_reg", "xgb_reg"}
CLASSIFICATION_MODELS = {"logistic_clf", "rf_clf", "xgb_clf"}

BASE_META_COLS = ["ticker", "quarter", "call_date", "entry_date", "exit_date", "split"]


def _benchmark_meta_col(df: pd.DataFrame, benchmark_return_col: str | None) -> str | None:
    if benchmark_return_col and benchmark_return_col in df.columns:
        return benchmark_return_col
    return None


def _meta_cols(
    df: pd.DataFrame,
    retain_benchmark_return: bool,
    benchmark_return_col: str | None,
) -> list[str]:
    meta_cols = list(BASE_META_COLS)
    benchmark_col = _benchmark_meta_col(df, benchmark_return_col)
    if retain_benchmark_return and benchmark_col is not None:
        meta_cols.append(benchmark_col)
    return meta_cols


def infer_task_type_from_target(target_name: str) -> str:
    if target_name in REGRESSION_TARGETS:
        return "regress"
    if target_name in CLASSIFICATION_TARGETS:
        return "classify"
    raise ValueError(
        f"Unknown target_name={target_name}. "
        f"Allowed regression targets: {sorted(REGRESSION_TARGETS)}; "
        f"allowed classification targets: {sorted(CLASSIFICATION_TARGETS)}."
    )


def check_model_target_compatibility(model_name: str, target_name: str) -> str:
    task_type = infer_task_type_from_target(target_name)

    if task_type == "regress" and model_name not in REGRESSION_MODELS:
        raise ValueError(
            f"target_name={target_name} is a regression target, but model_name={model_name} "
            f"is not a regression model. Allowed regression models: {sorted(REGRESSION_MODELS)}"
        )

    if task_type == "classify" and model_name not in CLASSIFICATION_MODELS:
        raise ValueError(
            f"target_name={target_name} is a classification target, but model_name={model_name} "
            f"is not a classification model. Allowed classification models: {sorted(CLASSIFICATION_MODELS)}"
        )

    return task_type


def select_feature_columns(df: pd.DataFrame, exclude: list[str]) -> list[str]:
    return [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]


def build_model_frames(
    df: pd.DataFrame,
    target_name: str,
    exclude: list[str],
    retain_benchmark_return: bool = False,
    benchmark_return_col: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    meta_cols = _meta_cols(df, retain_benchmark_return, benchmark_return_col)
    final_exclude = list(set(exclude + [target_name] + meta_cols))

    feature_cols = select_feature_columns(df, exclude=final_exclude)
    use_cols = feature_cols + meta_cols + [target_name]

    tmp = df[use_cols].copy()
    tmp = tmp.dropna(subset=[target_name]).reset_index(drop=True)

    train_df = tmp[tmp["split"] == "train"].copy()
    test_df = tmp[tmp["split"] == "test"].copy()

    non_const_cols = [c for c in feature_cols if train_df[c].nunique(dropna=False) > 1]
    feature_cols = non_const_cols

    X_train = train_df[feature_cols].fillna(0.0)
    X_test = test_df[feature_cols].fillna(0.0)

    train_df.loc[:, feature_cols] = X_train
    test_df.loc[:, feature_cols] = X_test

    keep_cols = feature_cols + meta_cols + [target_name]
    train_df = train_df[keep_cols].copy()
    test_df = test_df[keep_cols].copy()

    return train_df, test_df, feature_cols


def _build_prediction_df_regression(
    test_df: pd.DataFrame,
    pred,
    target_name: str,
    model_name: str,
    benchmark_return_col: str | None = None,
) -> pd.DataFrame:
    benchmark_col = _benchmark_meta_col(test_df, benchmark_return_col)
    extra_cols = [benchmark_col] if benchmark_col is not None else []
    meta_cols = [col for col in BASE_META_COLS + extra_cols if col in test_df.columns]
    out = test_df[meta_cols + [target_name]].copy()
    out = out.rename(columns={target_name: "y_true"})
    out["y_pred"] = pred
    out["model_name"] = model_name
    out["target_name"] = target_name
    out["task_type"] = "regress"
    return out


def _build_prediction_df_classification(
    test_df: pd.DataFrame,
    pred_label,
    pred_score,
    target_name: str,
    model_name: str,
    benchmark_return_col: str | None = None,
) -> pd.DataFrame:
    benchmark_col = _benchmark_meta_col(test_df, benchmark_return_col)
    extra_cols = [benchmark_col] if benchmark_col is not None else []
    meta_cols = [col for col in BASE_META_COLS + extra_cols if col in test_df.columns]
    out = test_df[meta_cols + [target_name]].copy()
    out = out.rename(columns={target_name: "y_true"})
    out["y_pred"] = pred_label
    if pred_score is not None:
        out["y_pred_score"] = pred_score
    out["model_name"] = model_name
    out["target_name"] = target_name
    out["task_type"] = "classify"
    return out


def fit_ridge_reg_predict(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: list[str],
    target_name: str,
    cfg: dict,
) -> tuple[object, pd.DataFrame]:
    check_model_target_compatibility("ridge_reg", target_name)

    model = Ridge(
        alpha=float(cfg.get("alpha", 8.0)),
        random_state=int(cfg.get("random_state", 42)),
    )
    model.fit(train_df[feature_cols], train_df[target_name])
    pred = model.predict(test_df[feature_cols])

    return model, _build_prediction_df_regression(
        test_df, pred, target_name, "ridge_reg", cfg.get("benchmark_return_col")
    )


def fit_rf_reg_predict(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: list[str],
    target_name: str,
    cfg: dict,
) -> tuple[object, pd.DataFrame]:
    check_model_target_compatibility("rf_reg", target_name)

    model = RandomForestRegressor(
        n_estimators=int(cfg.get("n_estimators", 200)),
        max_depth=None if cfg.get("max_depth", None) is None else int(cfg.get("max_depth")),
        min_samples_leaf=int(cfg.get("min_samples_leaf", 5)),
        min_samples_split=int(cfg.get("min_samples_split", 10)),
        max_features=cfg.get("max_features", "sqrt"),
        bootstrap=bool(cfg.get("bootstrap", True)),
        random_state=int(cfg.get("random_state", 42)),
        n_jobs=int(cfg.get("n_jobs", -1)),
    )
    model.fit(train_df[feature_cols], train_df[target_name])
    pred = model.predict(test_df[feature_cols])

    return model, _build_prediction_df_regression(
        test_df, pred, target_name, "rf_reg", cfg.get("benchmark_return_col")
    )


def fit_xgb_reg_predict(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: list[str],
    target_name: str,
    cfg: dict,
) -> tuple[object, pd.DataFrame]:
    check_model_target_compatibility("xgb_reg", target_name)

    model = XGBRegressor(
        n_estimators=int(cfg.get("n_estimators", 80)),
        max_depth=int(cfg.get("max_depth", 2)),
        learning_rate=float(cfg.get("learning_rate", 0.03)),
        subsample=float(cfg.get("subsample", 0.7)),
        colsample_bytree=float(cfg.get("colsample_bytree", 0.7)),
        reg_alpha=float(cfg.get("reg_alpha", 1.0)),
        reg_lambda=float(cfg.get("reg_lambda", 4.0)),
        min_child_weight=int(cfg.get("min_child_weight", 3)),
        gamma=float(cfg.get("gamma", 0.5)),
        random_state=int(cfg.get("random_state", 42)),
        objective="reg:squarederror",
        n_jobs=int(cfg.get("n_jobs", -1)),
    )
    model.fit(train_df[feature_cols], train_df[target_name])
    pred = model.predict(test_df[feature_cols])

    return model, _build_prediction_df_regression(
        test_df, pred, target_name, "xgb_reg", cfg.get("benchmark_return_col")
    )


def fit_logistic_clf_predict(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: list[str],
    target_name: str,
    cfg: dict,
) -> tuple[object, pd.DataFrame]:
    check_model_target_compatibility("logistic_clf", target_name)

    model = LogisticRegression(
        C=float(cfg.get("C", 0.2)),
        penalty=cfg.get("penalty", "l2"),
        solver=cfg.get("solver", "lbfgs"),
        class_weight=cfg.get("class_weight", "balanced"),
        max_iter=int(cfg.get("max_iter", 2000)),
        random_state=int(cfg.get("random_state", 42)),
    )
    model.fit(train_df[feature_cols], train_df[target_name])

    pred_label = model.predict(test_df[feature_cols])
    pred_proba = model.predict_proba(test_df[feature_cols])
    classes = list(model.classes_)
    if 1 in classes:
        pred_score = pred_proba[:, classes.index(1)]
    else:
        pred_score = pred_proba.max(axis=1)

    return model, _build_prediction_df_classification(
        test_df, pred_label, pred_score, target_name, "logistic_clf", cfg.get("benchmark_return_col")
    )


def fit_rf_clf_predict(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: list[str],
    target_name: str,
    cfg: dict,
) -> tuple[object, pd.DataFrame]:
    check_model_target_compatibility("rf_clf", target_name)

    model = RandomForestClassifier(
        n_estimators=int(cfg.get("n_estimators", 200)),
        max_depth=None if cfg.get("max_depth", None) is None else int(cfg.get("max_depth")),
        min_samples_leaf=int(cfg.get("min_samples_leaf", 5)),
        min_samples_split=int(cfg.get("min_samples_split", 10)),
        max_features=cfg.get("max_features", "sqrt"),
        bootstrap=bool(cfg.get("bootstrap", True)),
        class_weight=cfg.get("class_weight", "balanced_subsample"),
        random_state=int(cfg.get("random_state", 42)),
        n_jobs=int(cfg.get("n_jobs", -1)),
    )
    model.fit(train_df[feature_cols], train_df[target_name])

    pred_label = model.predict(test_df[feature_cols])
    pred_proba = model.predict_proba(test_df[feature_cols])
    classes = list(model.classes_)
    if 1 in classes:
        pred_score = pred_proba[:, classes.index(1)]
    else:
        pred_score = pred_proba.max(axis=1)

    return model, _build_prediction_df_classification(
        test_df, pred_label, pred_score, target_name, "rf_clf", cfg.get("benchmark_return_col")
    )


def fit_xgb_clf_predict(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: list[str],
    target_name: str,
    cfg: dict,
) -> tuple[object, pd.DataFrame]:
    check_model_target_compatibility("xgb_clf", target_name)

    train_y = pd.Series(train_df[target_name]).copy()
    classes = sorted(train_y.dropna().unique().tolist())
    class_to_index = {cls: idx for idx, cls in enumerate(classes)}
    index_to_class = {idx: cls for cls, idx in class_to_index.items()}
    y_train_encoded = train_y.map(class_to_index)

    num_class = max(len(classes), 2)
    objective = "binary:logistic" if len(classes) <= 2 else "multi:softprob"
    eval_metric = "logloss" if len(classes) <= 2 else "mlogloss"

    model = XGBClassifier(
        n_estimators=int(cfg.get("n_estimators", 80)),
        max_depth=int(cfg.get("max_depth", 2)),
        learning_rate=float(cfg.get("learning_rate", 0.03)),
        subsample=float(cfg.get("subsample", 0.7)),
        colsample_bytree=float(cfg.get("colsample_bytree", 0.7)),
        reg_alpha=float(cfg.get("reg_alpha", 1.0)),
        reg_lambda=float(cfg.get("reg_lambda", 4.0)),
        min_child_weight=int(cfg.get("min_child_weight", 3)),
        gamma=float(cfg.get("gamma", 0.5)),
        random_state=int(cfg.get("random_state", 42)),
        objective=cfg.get("objective", objective),
        eval_metric=cfg.get("eval_metric", eval_metric),
        num_class=num_class if len(classes) > 2 else None,
        n_jobs=int(cfg.get("n_jobs", -1)),
    )
    model.fit(train_df[feature_cols], y_train_encoded)

    pred_encoded = model.predict(test_df[feature_cols])
    pred_label = pd.Series(pred_encoded).map(index_to_class).to_numpy()

    pred_proba = model.predict_proba(test_df[feature_cols])
    if len(classes) == 2 and 1 in class_to_index:
        pred_score = pred_proba[:, class_to_index[1]]
    else:
        pred_score = pred_proba.max(axis=1)

    return model, _build_prediction_df_classification(
        test_df, pred_label, pred_score, target_name, "xgb_clf", cfg.get("benchmark_return_col")
    )


def evaluate_predictions(df_pred: pd.DataFrame) -> dict:
    if df_pred.empty:
        return {"n_test": 0}

    task_type = df_pred["task_type"].iloc[0]

    if task_type == "regress":
        y_true = df_pred["y_true"].values
        y_pred = df_pred["y_pred"].values

        mse = float(np.mean((y_true - y_pred) ** 2))
        mae = float(np.mean(np.abs(y_true - y_pred)))
        directional_accuracy = float(np.mean((y_true > 0) == (y_pred > 0)))
        ic = float(pd.Series(y_true).corr(pd.Series(y_pred), method="spearman"))

        return {
            "task_type": "regress",
            "n_test": int(len(df_pred)),
            "mse": mse,
            "mae": mae,
            "directional_accuracy": directional_accuracy,
            "spearman_ic": ic,
        }

    if task_type == "classify":
        y_true = df_pred["y_true"].values
        y_pred = df_pred["y_pred"].values

        accuracy = float(np.mean(y_true == y_pred))
        out = {
            "task_type": "classify",
            "n_test": int(len(df_pred)),
            "accuracy": accuracy,
        }

        if "y_pred_score" in df_pred.columns:
            y_score = df_pred["y_pred_score"].values
            pos_mask = y_pred == 1
            out["avg_positive_score"] = float(np.mean(y_score[pos_mask])) if np.any(pos_mask) else np.nan

        return out

    raise ValueError(f"Unknown task_type={task_type} in prediction dataframe.")
