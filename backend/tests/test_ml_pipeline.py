from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.data import encode_target, filter_cod_orders, temporal_split
from app.ml.evaluation import CostAssumptions, classification_metrics, threshold_analysis
from app.ml.features import (
    MODEL_FEATURES,
    add_derived_features,
    build_feature_frame,
    ensure_no_target_leakage,
)
from app.ml.rto_predictor import RTOPredictor, RiskThresholds, assign_risk_level
from app.ml.train import run_training
from data.generate import generate_orders


def sample_frame(rows: int = 300) -> pd.DataFrame:
    frame = pd.DataFrame(generate_orders(rows=rows, seed=123))
    frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True)
    return frame


def test_cod_filtering_keeps_only_cod_orders():
    cod = filter_cod_orders(sample_frame())

    assert set(cod["payment_method"]) == {"COD"}


def test_target_encoding_maps_rto_to_one_and_delivered_to_zero():
    frame = pd.DataFrame({"rto_outcome": ["RTO", "DELIVERED"]})

    assert encode_target(frame).tolist() == [1, 0]


def test_temporal_split_ordering_and_no_overlap():
    cod = filter_cod_orders(sample_frame(500))
    split = temporal_split(cod)

    assert split.train["created_at"].max() < split.validation["created_at"].min()
    assert split.validation["created_at"].max() < split.test["created_at"].min()
    assert set(split.train["order_id"]).isdisjoint(split.validation["order_id"])
    assert set(split.train["order_id"]).isdisjoint(split.test["order_id"])
    assert set(split.validation["order_id"]).isdisjoint(split.test["order_id"])


def test_feature_list_excludes_target_leakage_columns():
    assert "rto_outcome" not in MODEL_FEATURES
    assert "order_status" not in MODEL_FEATURES
    with pytest.raises(ValueError, match="target leakage"):
        ensure_no_target_leakage(MODEL_FEATURES + ["rto_outcome"])


def test_feature_frame_contains_expected_features_only():
    frame = sample_frame(20)
    features = build_feature_frame(frame)

    assert list(features.columns) == MODEL_FEATURES


def test_derived_feature_calculations_and_zero_denominators():
    frame = pd.DataFrame(
        {
            "amount": [99.0, 999.0],
            "previous_cod_orders": [0, 4],
            "previous_cod_refusals": [0, 1],
            "previous_successful_deliveries": [0, 2],
        }
    )

    enriched = add_derived_features(frame)

    assert enriched.loc[0, "refusal_rate"] == 0
    assert enriched.loc[0, "delivery_success_rate"] == 0
    assert enriched.loc[1, "refusal_rate"] == 0.25
    assert enriched.loc[1, "delivery_success_rate"] == 0.5
    assert enriched.loc[1, "order_history_depth"] == 6


def test_model_training_prediction_probability_and_reproducibility(tmp_path: Path):
    dataset_path = tmp_path / "orders.csv"
    pd.DataFrame(generate_orders(rows=800, seed=44)).to_csv(dataset_path, index=False)

    first = run_training(
        dataset_path=dataset_path,
        artifact_path=tmp_path / "first.joblib",
        report_path=tmp_path / "first.md",
        metrics_path=tmp_path / "first.json",
    )
    second = run_training(
        dataset_path=dataset_path,
        artifact_path=tmp_path / "second.joblib",
        report_path=tmp_path / "second.md",
        metrics_path=tmp_path / "second.json",
    )

    assert first["split_counts"] == second["split_counts"]
    assert first["calibrated_main_metrics"]["roc_auc"] == pytest.approx(
        second["calibrated_main_metrics"]["roc_auc"],
    )

    predictor = RTOPredictor.load(tmp_path / "first.joblib")
    order = filter_cod_orders(pd.read_csv(dataset_path)).iloc[0].to_dict()
    prediction = predictor.predict(order)

    assert 0 <= prediction["rto_probability"] <= 1
    assert prediction["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert prediction["explanation"]
    assert {"feature", "impact", "direction", "value"}.issubset(prediction["explanation"][0])


def test_risk_level_assignment_uses_configurable_thresholds():
    thresholds = RiskThresholds(medium=0.3, high=0.6)

    assert assign_risk_level(0.2, thresholds) == "LOW"
    assert assign_risk_level(0.4, thresholds) == "MEDIUM"
    assert assign_risk_level(0.7, thresholds) == "HIGH"


def test_evaluation_metrics_and_threshold_costs():
    y_true = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.7, 0.8, 0.2])

    metrics = classification_metrics(y_true, probabilities, threshold=0.5)
    thresholds = threshold_analysis(y_true, probabilities, [0.5], CostAssumptions(10, 50))

    assert metrics["confusion_matrix"] == {
        "true_negative": 1,
        "false_positive": 1,
        "false_negative": 1,
        "true_positive": 1,
    }
    assert thresholds[0]["total_cost"] == 60

