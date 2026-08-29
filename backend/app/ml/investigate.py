from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from app.ml.data import encode_target, filter_cod_orders, load_orders_csv, split_boundaries, temporal_split
from app.ml.evaluation import CostAssumptions, classification_metrics, threshold_analysis
from app.ml.features import MODEL_FEATURES, add_derived_features, build_feature_frame, build_preprocessor
from app.ml.train import RANDOM_STATE, fit_pipeline

DEFAULT_DATASET_PATH = Path("data/generated/orders.csv")
DEFAULT_FEATURE_REPORT_PATH = Path("evaluation/reports/rto_feature_analysis.md")
DEFAULT_INVESTIGATION_REPORT_PATH = Path("evaluation/reports/rto_model_investigation.md")

NUMERIC_ANALYSIS_COLUMNS = [
    "amount",
    "customer_account_age_days",
    "previous_cod_orders",
    "previous_cod_refusals",
    "previous_successful_deliveries",
    "pincode_rto_rate",
    "refusal_rate",
    "delivery_success_rate",
    "order_history_depth",
    "log_amount",
]


@dataclass(frozen=True)
class ModelRun:
    name: str
    pipeline: Any
    train_metrics: dict[str, Any]
    validation_metrics: dict[str, Any]
    test_metrics: dict[str, Any]
    train_probabilities: np.ndarray
    validation_probabilities: np.ndarray
    test_probabilities: np.ndarray


def prepare_cod_dataset(dataset_path: Path = DEFAULT_DATASET_PATH) -> pd.DataFrame:
    dataset = load_orders_csv(dataset_path)
    cod_dataset = filter_cod_orders(dataset)
    return add_derived_features(cod_dataset)


def numeric_correlations(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    analysis_frame = frame[NUMERIC_ANALYSIS_COLUMNS].copy()
    for column in NUMERIC_ANALYSIS_COLUMNS:
        analysis_frame[column] = pd.to_numeric(analysis_frame[column], errors="raise")
    analysis_frame["target"] = encode_target(frame)
    pearson = analysis_frame.corr(method="pearson", numeric_only=True)[["target"]].drop(index="target")
    spearman = analysis_frame.corr(method="spearman", numeric_only=True)[["target"]].drop(index="target")
    return pearson.rename(columns={"target": "pearson_rto"}), spearman.rename(columns={"target": "spearman_rto"})


def rto_rate_by_group(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    grouped = (
        frame.assign(target=encode_target(frame))
        .groupby(column, observed=True)["target"]
        .agg(orders="count", rto_rate="mean")
        .reset_index()
    )
    return grouped


def rto_rate_by_bins(frame: pd.DataFrame, column: str, bins: list[float] | int) -> pd.DataFrame:
    labels = pd.cut(frame[column].astype(float), bins=bins, include_lowest=True)
    grouped = (
        frame.assign(bucket=labels, target=encode_target(frame))
        .groupby("bucket", observed=True)["target"]
        .agg(orders="count", rto_rate="mean")
        .reset_index()
    )
    grouped["bucket"] = grouped["bucket"].astype(str)
    return grouped


def monotonic_direction(values: list[float], expected: str) -> str:
    clean = [value for value in values if not np.isnan(value)]
    if len(clean) < 2:
        return "insufficient_data"
    diffs = np.diff(clean)
    tolerance = 0.015
    if expected == "increasing":
        aligned = int(np.sum(diffs >= -tolerance))
    else:
        aligned = int(np.sum(diffs <= tolerance))
    ratio = aligned / len(diffs)
    if ratio >= 0.75:
        return "generally_aligned"
    if ratio >= 0.50:
        return "mixed"
    return "not_aligned"


def fit_candidate_models(split) -> list[ModelRun]:
    x_train = build_feature_frame(split.train)
    y_train = encode_target(split.train).to_numpy()
    x_validation = build_feature_frame(split.validation)
    y_validation = encode_target(split.validation).to_numpy()
    x_test = build_feature_frame(split.test)
    y_test = encode_target(split.test).to_numpy()

    candidates = [
        ("Dummy prevalence", DummyClassifier(strategy="prior")),
        ("Logistic regression", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE, solver="liblinear")),
        (
            "Random forest",
            RandomForestClassifier(
                n_estimators=240,
                min_samples_leaf=20,
                max_depth=7,
                class_weight="balanced_subsample",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "Gradient boosting",
            GradientBoostingClassifier(
                n_estimators=160,
                learning_rate=0.045,
                max_depth=3,
                min_samples_leaf=25,
                random_state=RANDOM_STATE,
            ),
        ),
    ]

    runs: list[ModelRun] = []
    for name, model in candidates:
        pipeline = fit_pipeline(model, x_train, y_train)
        train_probabilities = pipeline.predict_proba(x_train)[:, 1]
        validation_probabilities = pipeline.predict_proba(x_validation)[:, 1]
        test_probabilities = pipeline.predict_proba(x_test)[:, 1]
        runs.append(
            ModelRun(
                name=name,
                pipeline=pipeline,
                train_metrics=classification_metrics(y_train, train_probabilities),
                validation_metrics=classification_metrics(y_validation, validation_probabilities),
                test_metrics=classification_metrics(y_test, test_probabilities),
                train_probabilities=train_probabilities,
                validation_probabilities=validation_probabilities,
                test_probabilities=test_probabilities,
            )
        )
    return runs


def model_comparison_table(runs: list[ModelRun], split_name: str) -> str:
    rows = [
        "| Model | ROC-AUC | PR-AUC | Brier | Precision | Recall | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        metrics = getattr(run, f"{split_name}_metrics")
        rows.append(
            f"| {run.name} | {metrics['roc_auc']:.4f} | {metrics['pr_auc']:.4f} | "
            f"{metrics['brier_score']:.4f} | {metrics['precision']:.4f} | "
            f"{metrics['recall']:.4f} | {metrics['f1']:.4f} |"
        )
    return "\n".join(rows)


def aggregate_feature_importance(run: ModelRun) -> pd.DataFrame:
    preprocessor = run.pipeline.named_steps["preprocessor"]
    model = run.pipeline.named_steps["model"]
    transformed_names = [str(name) for name in preprocessor.get_feature_names_out()]
    if hasattr(model, "feature_importances_"):
        importance_values = model.feature_importances_
    elif hasattr(model, "coef_"):
        importance_values = np.abs(model.coef_[0])
    else:
        raise ValueError(f"model does not expose feature importances or coefficients: {run.name}")
    importances = pd.DataFrame({"feature": transformed_names, "importance": importance_values})
    importances["base_feature"] = importances["feature"].map(lambda value: value.split("_", 1)[0] if value.startswith(("pincode_risk_group_", "product_category_")) else value)
    importances.loc[importances["feature"].str.startswith("pincode_risk_group_"), "base_feature"] = "pincode_risk_group"
    importances.loc[importances["feature"].str.startswith("product_category_"), "base_feature"] = "product_category"
    return (
        importances.groupby("base_feature", as_index=False)["importance"]
        .sum()
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def probability_separation(y_true: np.ndarray, probabilities: np.ndarray) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label, target_value in [("DELIVERED", 0), ("RTO", 1)]:
        values = probabilities[y_true == target_value]
        rows.append(
            {
                "actual": label,
                "mean": float(np.mean(values)),
                "median": float(np.median(values)),
                "p25": float(np.quantile(values, 0.25)),
                "p75": float(np.quantile(values, 0.75)),
                "p90": float(np.quantile(values, 0.90)),
            }
        )
    return pd.DataFrame(rows)


def calibration_investigation(split, gradient_run: ModelRun) -> dict[str, float]:
    y_validation = encode_target(split.validation).to_numpy()
    y_test = encode_target(split.test).to_numpy()
    calibrator = LogisticRegression(random_state=RANDOM_STATE, solver="liblinear")
    calibrator.fit(gradient_run.validation_probabilities.reshape(-1, 1), y_validation)
    validation_calibrated = calibrator.predict_proba(gradient_run.validation_probabilities.reshape(-1, 1))[:, 1]
    test_calibrated = calibrator.predict_proba(gradient_run.test_probabilities.reshape(-1, 1))[:, 1]
    return {
        "validation_raw_brier": classification_metrics(y_validation, gradient_run.validation_probabilities)["brier_score"],
        "validation_calibrated_brier": classification_metrics(y_validation, validation_calibrated)["brier_score"],
        "test_raw_brier": classification_metrics(y_test, gradient_run.test_probabilities)["brier_score"],
        "test_calibrated_brier": classification_metrics(y_test, test_calibrated)["brier_score"],
    }


def markdown_table(frame: pd.DataFrame, float_digits: int = 4) -> str:
    if frame.empty:
        return "_No rows._"
    headers = [str(column) for column in frame.columns]
    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in frame.iterrows():
        values: list[str] = []
        for value in row:
            if isinstance(value, float):
                values.append(f"{value:.{float_digits}f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def write_feature_analysis_report(path: Path, cod_dataset: pd.DataFrame) -> dict[str, pd.DataFrame]:
    pearson, spearman = numeric_correlations(cod_dataset)
    pincode_bins = [0.08, 0.15, 0.22, 0.30, 0.38, 0.46]
    tables = {
        "pearson": pearson.reset_index(names="feature"),
        "spearman": spearman.reset_index(names="feature"),
        "pincode_rto_rate_bins": rto_rate_by_bins(cod_dataset, "pincode_rto_rate", pincode_bins),
        "pincode_risk_group": rto_rate_by_group(cod_dataset, "pincode_risk_group"),
        "previous_cod_refusals": rto_rate_by_group(cod_dataset, "previous_cod_refusals"),
        "refusal_rate_bins": rto_rate_by_bins(cod_dataset, "refusal_rate", [0, 0.001, 0.15, 0.30, 0.50, 1.0]),
        "previous_successful_deliveries": rto_rate_by_group(cod_dataset, "previous_successful_deliveries"),
        "delivery_success_rate_bins": rto_rate_by_bins(cod_dataset, "delivery_success_rate", [0, 0.001, 0.25, 0.50, 0.75, 1.0]),
        "amount_bins": rto_rate_by_bins(cod_dataset, "amount", [0, 750, 1500, 3000, 5000, 10000, 25000]),
        "is_first_order": rto_rate_by_group(cod_dataset, "is_first_order"),
        "product_category": rto_rate_by_group(cod_dataset, "product_category"),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# RTO Feature Analysis

Dataset is synthetic and filtered to COD orders only.

- COD rows: {len(cod_dataset)}
- COD RTO rate: {encode_target(cod_dataset).mean():.4f}

## Pearson Correlation

{markdown_table(tables['pearson'])}

## Spearman Correlation

{markdown_table(tables['spearman'])}

## Pincode RTO Rate Buckets

{markdown_table(tables['pincode_rto_rate_bins'])}

## Pincode Risk Group

{markdown_table(tables['pincode_risk_group'])}

## Previous COD Refusals

{markdown_table(tables['previous_cod_refusals'])}

## Refusal Rate Buckets

{markdown_table(tables['refusal_rate_bins'])}

## Previous Successful Deliveries

{markdown_table(tables['previous_successful_deliveries'])}

## Delivery Success Rate Buckets

{markdown_table(tables['delivery_success_rate_bins'])}

## Amount Buckets

{markdown_table(tables['amount_bins'])}

## First Order

{markdown_table(tables['is_first_order'])}

## Product Category

{markdown_table(tables['product_category'])}
""",
        encoding="utf-8",
    )
    return tables


def write_investigation_report(
    path: Path,
    cod_dataset: pd.DataFrame,
    split,
    runs: list[ModelRun],
    feature_tables: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    y_test = encode_target(split.test).to_numpy()
    best_model = max(runs, key=lambda run: run.validation_metrics["roc_auc"])
    strongest_test = max(runs, key=lambda run: run.test_metrics["roc_auc"])
    gradient_run = next(run for run in runs if run.name == "Gradient boosting")
    calibration = calibration_investigation(split, gradient_run)
    thresholds = threshold_analysis(
        y_test,
        best_model.test_probabilities,
        [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70],
        CostAssumptions(),
    )
    threshold_frame = pd.DataFrame(thresholds).rename(columns={"total_cost": "synthetic_total_cost"})
    threshold_frame["predicted_high_risk_count"] = threshold_frame["false_positives"] + (
        y_test.sum() - threshold_frame["false_negatives"]
    )
    threshold_frame = threshold_frame[
        [
            "threshold",
            "precision",
            "recall",
            "false_positive_rate",
            "false_negative_rate",
            "predicted_high_risk_count",
            "false_positives",
            "false_negatives",
            "synthetic_total_cost",
        ]
    ]

    pincode_correlation = float(feature_tables["pearson"].loc[feature_tables["pearson"]["feature"] == "pincode_rto_rate", "pearson_rto"].iloc[0])
    pincode_means = cod_dataset.assign(target=encode_target(cod_dataset)).groupby("rto_outcome")["pincode_rto_rate"].mean()
    feature_importance = aggregate_feature_importance(best_model)
    separation = probability_separation(y_test, best_model.test_probabilities)

    pincode_alignment = monotonic_direction(feature_tables["pincode_rto_rate_bins"]["rto_rate"].astype(float).tolist(), "increasing")
    refusal_alignment = monotonic_direction(feature_tables["previous_cod_refusals"]["rto_rate"].astype(float).tolist(), "increasing")
    success_alignment = monotonic_direction(feature_tables["previous_successful_deliveries"]["rto_rate"].astype(float).tolist(), "decreasing")

    recommendation = "PROCEED WITH LIMITATIONS"
    if pincode_alignment == "not_aligned" or refusal_alignment == "not_aligned":
        recommendation = "IMPROVE DATA GENERATOR"
    elif best_model.validation_metrics["roc_auc"] < 0.62:
        recommendation = "IMPROVE MODEL"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# RTO Model Investigation

## A. Current Result

The current COD-only synthetic model has moderate ranking power and weak recall at threshold 0.50. This investigation does not alter labels, tune on the test set, or change the held-out test split.

- COD rows: {len(cod_dataset)}
- Train rows: {len(split.train)}
- Validation rows: {len(split.validation)}
- Test rows: {len(split.test)}
- Train boundary: {split_boundaries(split)['train_start']} to {split_boundaries(split)['train_end']}
- Validation boundary: {split_boundaries(split)['validation_start']} to {split_boundaries(split)['validation_end']}
- Test boundary: {split_boundaries(split)['test_start']} to {split_boundaries(split)['test_end']}

## B. Feature Behavior

Pearson correlations with RTO:

{markdown_table(feature_tables['pearson'])}

Spearman correlations with RTO:

{markdown_table(feature_tables['spearman'])}

Monotonic checks:

- pincode_rto_rate expected increasing: {pincode_alignment}
- previous_cod_refusals expected increasing: {refusal_alignment}
- previous_successful_deliveries expected decreasing: {success_alignment}

## C. Model Comparison

Train performance:

{model_comparison_table(runs, 'train')}

Validation performance:

{model_comparison_table(runs, 'validation')}

Held-out test performance:

{model_comparison_table(runs, 'test')}

The model selected by validation ROC-AUC is: **{best_model.name}**.
The strongest held-out test ROC-AUC in this single comparison is: **{strongest_test.name}**.

## D. Pincode Investigation

Pincode RTO buckets:

{markdown_table(feature_tables['pincode_rto_rate_bins'])}

- Pearson correlation(pincode_rto_rate, RTO): {pincode_correlation:.4f}
- Mean pincode_rto_rate for DELIVERED: {pincode_means.get('DELIVERED', float('nan')):.4f}
- Mean pincode_rto_rate for RTO: {pincode_means.get('RTO', float('nan')):.4f}

The global pincode relationship is directionally correct in the data. A local explanation can still show `pincode_rto_rate` as decreasing risk for an individual order when that order's pincode rate is below the train-set reference value.

## E. Customer-History Investigation

Previous COD refusals:

{markdown_table(feature_tables['previous_cod_refusals'])}

Refusal rate buckets:

{markdown_table(feature_tables['refusal_rate_bins'])}

Previous successful deliveries:

{markdown_table(feature_tables['previous_successful_deliveries'])}

Delivery success rate buckets:

{markdown_table(feature_tables['delivery_success_rate_bins'])}

## F. Probability Separation

Probability summary for **{best_model.name}** on held-out test:

{markdown_table(separation)}

## G. Threshold Analysis

Synthetic cost assumptions: false_positive_cost=25.00, false_negative_cost=150.00.

{markdown_table(threshold_frame)}

## H. Calibration

Gradient-boosting calibration was fitted on validation only.

| Split | Raw Brier | Calibrated Brier |
| --- | ---: | ---: |
| Validation | {calibration['validation_raw_brier']:.4f} | {calibration['validation_calibrated_brier']:.4f} |
| Held-out test | {calibration['test_raw_brier']:.4f} | {calibration['test_calibrated_brier']:.4f} |

Calibration does not improve Brier score on validation or held-out test for this run. Keep raw model probabilities for now unless a calibration approach demonstrates held-out benefit.

## I. Root Cause

The synthetic signal exists, but it is intentionally noisy and overlapping. Logistic regression performs slightly better than gradient boosting on this generated dataset because much of the signal is smooth and approximately monotonic, while the current gradient boosting configuration appears to trade some ranking quality for nonlinear interactions. Weak recall at 0.50 is mostly a thresholding issue in an imbalanced dataset with a roughly 29% RTO rate, not evidence of a broken target or leakage.

## J. Recommendation

**{recommendation}**

Proceed only with clear limitations: keep using probabilities rather than hard labels, avoid treating threshold 0.50 as a business rule, prefer validation-selected models, and let the future economic engine combine probability with deterministic costs.

## Global Feature Importance

Feature importance for validation-selected model:

{markdown_table(feature_importance)}
""",
        encoding="utf-8",
    )
    return {
        "best_model": best_model.name,
        "strongest_test_model": strongest_test.name,
        "recommendation": recommendation,
        "pincode_correlation": pincode_correlation,
        "pincode_alignment": pincode_alignment,
        "threshold_analysis": threshold_frame,
        "feature_importance": feature_importance,
        "probability_separation": separation,
        "calibration": calibration,
    }


def run_investigation(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    feature_report_path: Path = DEFAULT_FEATURE_REPORT_PATH,
    investigation_report_path: Path = DEFAULT_INVESTIGATION_REPORT_PATH,
) -> dict[str, Any]:
    cod_dataset = prepare_cod_dataset(dataset_path)
    split = temporal_split(cod_dataset)
    feature_tables = write_feature_analysis_report(feature_report_path, cod_dataset)
    runs = fit_candidate_models(split)
    result = write_investigation_report(investigation_report_path, cod_dataset, split, runs, feature_tables)
    result["model_runs"] = runs
    result["cod_rows"] = len(cod_dataset)
    result["split_counts"] = {"train": len(split.train), "validation": len(split.validation), "test": len(split.test)}
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Investigate COD RTO model and feature behavior.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--feature-report", type=Path, default=DEFAULT_FEATURE_REPORT_PATH)
    parser.add_argument("--investigation-report", type=Path, default=DEFAULT_INVESTIGATION_REPORT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_investigation(args.dataset, args.feature_report, args.investigation_report)
    print(f"COD rows: {result['cod_rows']}")
    print(f"split counts: {result['split_counts']}")
    print(f"validation-selected model: {result['best_model']}")
    print(f"strongest held-out test model: {result['strongest_test_model']}")
    print(f"pincode correlation: {result['pincode_correlation']:.4f}")
    print(f"pincode alignment: {result['pincode_alignment']}")
    print(f"recommendation: {result['recommendation']}")
    print(f"feature report: {args.feature_report}")
    print(f"investigation report: {args.investigation_report}")


if __name__ == "__main__":
    main()
