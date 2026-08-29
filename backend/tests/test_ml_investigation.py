from pathlib import Path

import pandas as pd

from app.ml.investigate import (
    monotonic_direction,
    numeric_correlations,
    rto_rate_by_bins,
    run_investigation,
)
from data.generate import generate_orders


def test_numeric_correlations_include_pincode_rto_rate():
    frame = pd.DataFrame(generate_orders(rows=500, seed=42))
    frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True)
    frame = frame[frame["payment_method"] == "COD"].copy()
    frame["refusal_rate"] = 0.0
    nonzero = frame["previous_cod_orders"] > 0
    frame.loc[nonzero, "refusal_rate"] = frame.loc[nonzero, "previous_cod_refusals"] / frame.loc[nonzero, "previous_cod_orders"]
    frame["delivery_success_rate"] = 0.0
    frame.loc[nonzero, "delivery_success_rate"] = (
        frame.loc[nonzero, "previous_successful_deliveries"] / frame.loc[nonzero, "previous_cod_orders"]
    )
    frame["order_history_depth"] = frame["previous_cod_orders"] + frame["previous_successful_deliveries"]
    frame["log_amount"] = 1.0

    pearson, spearman = numeric_correlations(frame)

    assert "pincode_rto_rate" in pearson.index
    assert "pincode_rto_rate" in spearman.index


def test_rto_rate_by_bins_returns_order_counts():
    frame = pd.DataFrame(
        {
            "amount": [100, 200, 800, 1200],
            "rto_outcome": ["DELIVERED", "RTO", "RTO", "DELIVERED"],
        }
    )

    result = rto_rate_by_bins(frame, "amount", [0, 500, 1500])

    assert result["orders"].sum() == 4


def test_monotonic_direction_classifies_relationships():
    assert monotonic_direction([0.1, 0.2, 0.3], "increasing") == "generally_aligned"
    assert monotonic_direction([0.3, 0.2, 0.1], "decreasing") == "generally_aligned"
    assert monotonic_direction([0.3, 0.2, 0.1], "increasing") == "not_aligned"


def test_run_investigation_writes_reports(tmp_path: Path):
    dataset_path = tmp_path / "orders.csv"
    feature_report = tmp_path / "feature.md"
    investigation_report = tmp_path / "investigation.md"
    pd.DataFrame(generate_orders(rows=900, seed=51)).to_csv(dataset_path, index=False)

    result = run_investigation(dataset_path, feature_report, investigation_report)

    assert result["cod_rows"] > 0
    assert result["best_model"] in {"Dummy prevalence", "Logistic regression", "Random forest", "Gradient boosting"}
    assert result["recommendation"] in {"PROCEED", "IMPROVE MODEL", "IMPROVE DATA GENERATOR", "PROCEED WITH LIMITATIONS"}
    assert feature_report.exists()
    assert investigation_report.exists()

