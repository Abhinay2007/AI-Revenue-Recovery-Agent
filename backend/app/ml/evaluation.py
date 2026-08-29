from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass(frozen=True)
class CostAssumptions:
    false_positive_cost: float = 25.0
    false_negative_cost: float = 150.0


def classification_metrics(y_true: np.ndarray, probabilities: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    predictions = probabilities >= threshold
    matrix = confusion_matrix(y_true, predictions, labels=[0, 1])
    return {
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, predictions)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "confusion_matrix": {
            "true_negative": int(matrix[0, 0]),
            "false_positive": int(matrix[0, 1]),
            "false_negative": int(matrix[1, 0]),
            "true_positive": int(matrix[1, 1]),
        },
    }


def threshold_analysis(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    thresholds: list[float],
    costs: CostAssumptions,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        predictions = probabilities >= threshold
        tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
        negatives = tn + fp
        positives = tp + fn
        total_cost = fp * costs.false_positive_cost + fn * costs.false_negative_cost
        rows.append(
            {
                "threshold": threshold,
                "precision": float(precision_score(y_true, predictions, zero_division=0)),
                "recall": float(recall_score(y_true, predictions, zero_division=0)),
                "false_positive_rate": float(fp / negatives) if negatives else 0.0,
                "false_negative_rate": float(fn / positives) if positives else 0.0,
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "total_cost": float(total_cost),
            }
        )
    return rows


def calibration_bins(y_true: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    edges = np.linspace(0, 1, bins + 1)
    rows: list[dict[str, float]] = []
    for index in range(bins):
        left = edges[index]
        right = edges[index + 1]
        if index == bins - 1:
            mask = (probabilities >= left) & (probabilities <= right)
        else:
            mask = (probabilities >= left) & (probabilities < right)
        if not np.any(mask):
            continue
        rows.append(
            {
                "bin_start": float(left),
                "bin_end": float(right),
                "mean_predicted_probability": float(np.mean(probabilities[mask])),
                "observed_rto_rate": float(np.mean(y_true[mask])),
                "count": int(np.sum(mask)),
            }
        )
    return rows


def format_metric_block(metrics: dict[str, Any]) -> str:
    matrix = metrics["confusion_matrix"]
    return "\n".join(
        [
            f"- ROC-AUC: {metrics['roc_auc']:.4f}",
            f"- PR-AUC: {metrics['pr_auc']:.4f}",
            f"- Precision: {metrics['precision']:.4f}",
            f"- Recall: {metrics['recall']:.4f}",
            f"- F1: {metrics['f1']:.4f}",
            f"- Accuracy: {metrics['accuracy']:.4f}",
            f"- Brier score: {metrics['brier_score']:.4f}",
            (
                "- Confusion matrix: "
                f"TN={matrix['true_negative']}, FP={matrix['false_positive']}, "
                f"FN={matrix['false_negative']}, TP={matrix['true_positive']}"
            ),
        ]
    )


def write_report(path: Path, sections: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    threshold_rows = sections["threshold_analysis"]
    calibration_rows = sections["calibration_bins"]

    threshold_table = "\n".join(
        [
            "| Threshold | Precision | Recall | FPR | FNR | FP | FN | Synthetic cost |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *[
                (
                    f"| {row['threshold']:.2f} | {row['precision']:.4f} | {row['recall']:.4f} | "
                    f"{row['false_positive_rate']:.4f} | {row['false_negative_rate']:.4f} | "
                    f"{row['false_positives']} | {row['false_negatives']} | {row['total_cost']:.2f} |"
                )
                for row in threshold_rows
            ],
        ]
    )
    calibration_table = "\n".join(
        [
            "| Bin | Mean predicted | Observed RTO rate | Count |",
            "| --- | ---: | ---: | ---: |",
            *[
                (
                    f"| {row['bin_start']:.1f}-{row['bin_end']:.1f} | "
                    f"{row['mean_predicted_probability']:.4f} | {row['observed_rto_rate']:.4f} | {row['count']} |"
                )
                for row in calibration_rows
            ],
        ]
    )

    content = f"""# RTO Model Evaluation Report

This report uses a synthetic dataset. Metrics should not be interpreted as real-world production performance.

## Dataset

- Total rows: {sections['dataset_size']}
- COD rows: {sections['cod_size']}
- Target encoding: RTO = 1, DELIVERED = 0
- COD RTO rate: {sections['cod_rto_rate']:.4f}

## Class Distribution

{sections['class_distribution']}

## Temporal Split

- Train rows: {sections['split_counts']['train']}
- Validation rows: {sections['split_counts']['validation']}
- Test rows: {sections['split_counts']['test']}
- Train: {sections['split_boundaries']['train_start']} to {sections['split_boundaries']['train_end']}
- Validation: {sections['split_boundaries']['validation_start']} to {sections['split_boundaries']['validation_end']}
- Test: {sections['split_boundaries']['test_start']} to {sections['split_boundaries']['test_end']}

The held-out test set contains later orders than the training and validation sets and was not used for model selection or calibration fitting.

## Feature List

{sections['feature_list']}

## Leakage Exclusions

Excluded from model features:

{sections['leakage_exclusions']}

## Baseline A: Training Prevalence

{format_metric_block(sections['prevalence_metrics'])}

## Baseline B: Logistic Regression

{format_metric_block(sections['logistic_metrics'])}

## Main Model: Gradient Boosting

Raw model on held-out test:

{format_metric_block(sections['raw_main_metrics'])}

Calibrated model on held-out test:

{format_metric_block(sections['calibrated_main_metrics'])}

## Threshold Analysis

Thresholds are candidates for analysis only. The future economic decision engine should combine risk probability with deterministic economics and merchant policy.

{threshold_table}

## Calibration

- Brier score before calibration: {sections['raw_main_metrics']['brier_score']:.4f}
- Brier score after calibration: {sections['calibrated_main_metrics']['brier_score']:.4f}
- Calibration method: logistic calibration fitted on the validation split only.

{calibration_table}

## Explainability Readiness

The saved prediction service returns feature-level explanation metadata for individual predictions. The current implementation uses model-derived single-feature perturbation against train-set reference values and reports the resulting calibrated probability impact.

SHAP is not implemented in this milestone. The explanation output is suitable metadata for debugging and future UI work, but should be validated before production use.

## Synthetic Cost Assumptions

- False-positive cost: {sections['cost_assumptions'].false_positive_cost:.2f}
- False-negative cost: {sections['cost_assumptions'].false_negative_cost:.2f}

These are synthetic evaluation assumptions used to demonstrate methodology, not real merchant costs.

## Limitations

- The dataset is synthetic and generated from known assumptions.
- Pincode risk statistics are synthetic historical signals, not production aggregates.
- The model is trained only for COD orders.
- Raw pincode, identifiers, `order_status`, and `rto_outcome` are excluded from features.
- The model estimates RTO probability only; it does not decide recovery actions.
"""
    path.write_text(content, encoding="utf-8")
