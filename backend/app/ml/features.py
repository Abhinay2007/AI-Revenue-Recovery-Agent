from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder

TARGET_COLUMN = "rto_outcome"
TARGET_POSITIVE_LABEL = "RTO"
TARGET_NEGATIVE_LABEL = "DELIVERED"

NUMERIC_FEATURES = [
    "amount",
    "customer_account_age_days",
    "previous_cod_orders",
    "previous_cod_refusals",
    "previous_successful_deliveries",
    "pincode_rto_rate",
]
CATEGORICAL_FEATURES = ["pincode_risk_group", "product_category"]
BOOLEAN_FEATURES = ["is_first_order"]
DERIVED_FEATURES = ["refusal_rate", "delivery_success_rate", "order_history_depth", "log_amount"]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES + BOOLEAN_FEATURES + DERIVED_FEATURES
LEAKAGE_COLUMNS = {"rto_outcome", "order_status"}
EXCLUDED_FEATURES = {
    "order_id",
    "customer_id",
    "pincode",
    "order_status",
    "rto_outcome",
    "payment_method",
    "created_at",
}


def ensure_no_target_leakage(feature_columns: list[str]) -> None:
    leaked_columns = sorted(set(feature_columns) & LEAKAGE_COLUMNS)
    if leaked_columns:
        raise ValueError(f"target leakage detected in feature set: {leaked_columns}")


def coerce_bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().map({"true": True, "false": False, "1": True, "0": False})


def add_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    previous_cod_orders = enriched["previous_cod_orders"].astype(float)
    previous_refusals = enriched["previous_cod_refusals"].astype(float)
    previous_successes = enriched["previous_successful_deliveries"].astype(float)

    enriched["refusal_rate"] = np.where(previous_cod_orders > 0, previous_refusals / previous_cod_orders, 0.0)
    enriched["delivery_success_rate"] = np.where(
        previous_cod_orders > 0,
        previous_successes / previous_cod_orders,
        0.0,
    )
    enriched["order_history_depth"] = previous_cod_orders + previous_successes
    enriched["log_amount"] = np.log1p(enriched["amount"].astype(float))
    return enriched


def build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    ensure_no_target_leakage(MODEL_FEATURES)
    enriched = add_derived_features(frame)
    missing = sorted(set(MODEL_FEATURES) - set(enriched.columns))
    if missing:
        raise ValueError(f"missing model features: {missing}")

    feature_frame = enriched[MODEL_FEATURES].copy()
    for column in NUMERIC_FEATURES + DERIVED_FEATURES:
        feature_frame[column] = pd.to_numeric(feature_frame[column], errors="raise")
    for column in CATEGORICAL_FEATURES:
        feature_frame[column] = feature_frame[column].astype(str)
    for column in BOOLEAN_FEATURES:
        feature_frame[column] = coerce_bool_series(feature_frame[column]).astype(int)
    return feature_frame


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", NUMERIC_FEATURES + BOOLEAN_FEATURES + DERIVED_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def get_transformed_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    return [str(name) for name in preprocessor.get_feature_names_out()]

