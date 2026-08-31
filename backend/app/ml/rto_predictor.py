from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.core.config import get_default_artifact_path
from app.ml.features import MODEL_FEATURES, build_feature_frame

DEFAULT_ARTIFACT_PATH = get_default_artifact_path()


@dataclass(frozen=True)
class RiskThresholds:
    medium: float = 0.35
    high: float = 0.55


def assign_risk_level(probability: float, thresholds: RiskThresholds) -> str:
    if probability >= thresholds.high:
        return "HIGH"
    if probability >= thresholds.medium:
        return "MEDIUM"
    return "LOW"


class RTOPredictor:
    def __init__(self, artifact: dict[str, Any]) -> None:
        self.pipeline = artifact["pipeline"]
        self.calibrator = artifact["calibrator"]
        self.risk_thresholds = RiskThresholds(**artifact.get("risk_thresholds", {}))
        self.explanation_reference = artifact["explanation_reference"]

    @classmethod
    def load(cls, path: Path = DEFAULT_ARTIFACT_PATH) -> "RTOPredictor":
        if not path.exists():
            raise FileNotFoundError(f"model artifact not found: {path}")
        return cls(joblib.load(path))

    def predict(self, order_features: dict[str, Any]) -> dict[str, Any]:
        frame = pd.DataFrame([order_features])
        features = build_feature_frame(frame)
        raw_probability = float(self.pipeline.predict_proba(features)[:, 1][0])
        probability = float(self.calibrator.predict_proba([[raw_probability]])[:, 1][0])
        return {
            "rto_probability": probability,
            "risk_level": assign_risk_level(probability, self.risk_thresholds),
            "explanation": self.explain(features),
        }

    def probability_for_feature_frame(self, feature_frame: pd.DataFrame) -> float:
        raw_probability = float(self.pipeline.predict_proba(feature_frame)[:, 1][0])
        return float(self.calibrator.predict_proba([[raw_probability]])[:, 1][0])

    def explain(self, feature_frame: pd.DataFrame, top_n: int = 5) -> list[dict[str, Any]]:
        current_probability = self.probability_for_feature_frame(feature_frame)
        explanations: list[dict[str, Any]] = []
        for feature in MODEL_FEATURES:
            perturbed = feature_frame.copy()
            perturbed[feature] = self.explanation_reference[feature]
            impact = current_probability - self.probability_for_feature_frame(perturbed)
            value = feature_frame.iloc[0][feature]
            explanations.append(
                {
                    "feature": feature,
                    "impact": impact,
                    "direction": "increases_risk" if impact >= 0 else "decreases_risk",
                    "value": float(value) if isinstance(value, Real) else str(value),
                }
            )
        return sorted(explanations, key=lambda item: abs(item["impact"]), reverse=True)[:top_n]
