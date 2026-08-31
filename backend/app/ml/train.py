from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from pandas.api.types import is_numeric_dtype
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.core.config import get_default_artifact_path, get_default_dataset_path
from app.ml.data import encode_target, filter_cod_orders, load_orders_csv, split_boundaries, temporal_split
from app.ml.evaluation import (
    CostAssumptions,
    calibration_bins,
    classification_metrics,
    threshold_analysis,
    write_report,
)
from app.ml.features import EXCLUDED_FEATURES, MODEL_FEATURES, build_feature_frame, build_preprocessor
from app.ml.rto_predictor import RiskThresholds

DEFAULT_DATASET_PATH = get_default_dataset_path()
DEFAULT_ARTIFACT_PATH = get_default_artifact_path()
DEFAULT_REPORT_PATH = Path("evaluation/reports/rto_model_report.md")
DEFAULT_METADATA_PATH = Path("evaluation/reports/rto_model_metrics.json")
RANDOM_STATE = 42


def build_explanation_reference(x_train) -> dict[str, Any]:
    reference: dict[str, Any] = {}
    for column in x_train.columns:
        if is_numeric_dtype(x_train[column]):
            reference[column] = float(x_train[column].median())
        else:
            reference[column] = str(x_train[column].mode().iloc[0])
    return reference


def fit_pipeline(model: Any, x_train, y_train) -> Pipeline:
    pipeline = Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            ("model", model),
        ]
    )
    pipeline.fit(x_train, y_train)
    return pipeline


def train_models(split) -> dict[str, Any]:
    x_train = build_feature_frame(split.train)
    y_train = encode_target(split.train).to_numpy()
    x_validation = build_feature_frame(split.validation)
    y_validation = encode_target(split.validation).to_numpy()
    x_test = build_feature_frame(split.test)
    y_test = encode_target(split.test).to_numpy()

    prevalence_pipeline = fit_pipeline(DummyClassifier(strategy="prior"), x_train, y_train)
    logistic_pipeline = fit_pipeline(
        LogisticRegression(max_iter=1000, random_state=RANDOM_STATE, solver="liblinear"),
        x_train,
        y_train,
    )
    main_pipeline = fit_pipeline(
        GradientBoostingClassifier(
            n_estimators=160,
            learning_rate=0.045,
            max_depth=3,
            min_samples_leaf=25,
            random_state=RANDOM_STATE,
        ),
        x_train,
        y_train,
    )

    validation_raw_probabilities = main_pipeline.predict_proba(x_validation)[:, 1]
    calibrator = LogisticRegression(random_state=RANDOM_STATE, solver="liblinear")
    calibrator.fit(validation_raw_probabilities.reshape(-1, 1), y_validation)

    return {
        "x_train": x_train,
        "y_train": y_train,
        "x_validation": x_validation,
        "y_validation": y_validation,
        "x_test": x_test,
        "y_test": y_test,
        "prevalence_pipeline": prevalence_pipeline,
        "logistic_pipeline": logistic_pipeline,
        "main_pipeline": main_pipeline,
        "calibrator": calibrator,
        "explanation_reference": build_explanation_reference(x_train),
    }


def class_distribution(name: str, y: np.ndarray) -> str:
    positives = int(y.sum())
    total = len(y)
    return f"- {name}: rows={total}, RTO={positives} ({positives / total:.4f}), DELIVERED={total - positives}"


def build_report_sections(dataset, cod_dataset, split, training_output, thresholds, costs) -> dict[str, Any]:
    y_train = training_output["y_train"]
    y_validation = training_output["y_validation"]
    y_test = training_output["y_test"]
    x_test = training_output["x_test"]

    prevalence_probabilities = training_output["prevalence_pipeline"].predict_proba(x_test)[:, 1]
    logistic_probabilities = training_output["logistic_pipeline"].predict_proba(x_test)[:, 1]
    raw_main_probabilities = training_output["main_pipeline"].predict_proba(x_test)[:, 1]
    calibrated_probabilities = training_output["calibrator"].predict_proba(raw_main_probabilities.reshape(-1, 1))[:, 1]

    cod_target = encode_target(cod_dataset).to_numpy()
    threshold_rows = threshold_analysis(y_test, calibrated_probabilities, thresholds, costs)

    return {
        "dataset_size": len(dataset),
        "cod_size": len(cod_dataset),
        "cod_rto_rate": float(np.mean(cod_target)),
        "split_counts": {
            "train": len(split.train),
            "validation": len(split.validation),
            "test": len(split.test),
        },
        "split_rto_rates": {
            "train": float(np.mean(y_train)),
            "validation": float(np.mean(y_validation)),
            "test": float(np.mean(y_test)),
        },
        "split_boundaries": split_boundaries(split),
        "class_distribution": "\n".join(
            [
                class_distribution("Train", y_train),
                class_distribution("Validation", y_validation),
                class_distribution("Test", y_test),
            ]
        ),
        "feature_list": "\n".join([f"- {feature}" for feature in MODEL_FEATURES]),
        "leakage_exclusions": "\n".join([f"- {feature}" for feature in sorted(EXCLUDED_FEATURES)]),
        "prevalence_metrics": classification_metrics(y_test, prevalence_probabilities),
        "logistic_metrics": classification_metrics(y_test, logistic_probabilities),
        "raw_main_metrics": classification_metrics(y_test, raw_main_probabilities),
        "calibrated_main_metrics": classification_metrics(y_test, calibrated_probabilities),
        "threshold_analysis": threshold_rows,
        "calibration_bins": calibration_bins(y_test, calibrated_probabilities),
        "cost_assumptions": costs,
    }


def save_artifact(path: Path, training_output: dict[str, Any], risk_thresholds: RiskThresholds) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "pipeline": training_output["main_pipeline"],
        "calibrator": training_output["calibrator"],
        "feature_columns": MODEL_FEATURES,
        "risk_thresholds": {"medium": risk_thresholds.medium, "high": risk_thresholds.high},
        "explanation_reference": training_output["explanation_reference"],
        "target_encoding": {"RTO": 1, "DELIVERED": 0},
    }
    joblib.dump(artifact, path)


def write_metrics_json(path: Path, sections: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        key: value
        for key, value in sections.items()
        if key not in {"cost_assumptions", "calibration_bins", "threshold_analysis"}
    }
    serializable["threshold_analysis"] = sections["threshold_analysis"]
    serializable["calibration_bins"] = sections["calibration_bins"]
    serializable["cost_assumptions"] = {
        "false_positive_cost": sections["cost_assumptions"].false_positive_cost,
        "false_negative_cost": sections["cost_assumptions"].false_negative_cost,
    }
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")


def run_training(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    metrics_path: Path = DEFAULT_METADATA_PATH,
    costs: CostAssumptions = CostAssumptions(),
    risk_thresholds: RiskThresholds = RiskThresholds(),
) -> dict[str, Any]:
    dataset = load_orders_csv(dataset_path)
    cod_dataset = filter_cod_orders(dataset)
    split = temporal_split(cod_dataset)
    training_output = train_models(split)
    thresholds = [0.30, 0.40, 0.50, 0.60, 0.70]
    sections = build_report_sections(dataset, cod_dataset, split, training_output, thresholds, costs)
    save_artifact(artifact_path, training_output, risk_thresholds)
    write_report(report_path, sections)
    write_metrics_json(metrics_path, sections)
    return sections


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and evaluate the COD RTO risk model.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--false-positive-cost", type=float, default=25.0)
    parser.add_argument("--false-negative-cost", type=float, default=150.0)
    parser.add_argument("--medium-risk-threshold", type=float, default=0.35)
    parser.add_argument("--high-risk-threshold", type=float, default=0.55)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sections = run_training(
        dataset_path=args.dataset,
        artifact_path=args.artifact,
        report_path=args.report,
        metrics_path=args.metrics,
        costs=CostAssumptions(args.false_positive_cost, args.false_negative_cost),
        risk_thresholds=RiskThresholds(args.medium_risk_threshold, args.high_risk_threshold),
    )
    print(f"COD rows: {sections['cod_size']}")
    print(f"split counts: {sections['split_counts']}")
    print(f"split RTO rates: {sections['split_rto_rates']}")
    print(f"main ROC-AUC: {sections['calibrated_main_metrics']['roc_auc']:.4f}")
    print(f"main PR-AUC: {sections['calibrated_main_metrics']['pr_auc']:.4f}")
    print(f"Brier raw: {sections['raw_main_metrics']['brier_score']:.4f}")
    print(f"Brier calibrated: {sections['calibrated_main_metrics']['brier_score']:.4f}")
    print(f"artifact: {args.artifact}")
    print(f"report: {args.report}")


if __name__ == "__main__":
    main()
