from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.ml.features import TARGET_NEGATIVE_LABEL, TARGET_POSITIVE_LABEL


@dataclass(frozen=True)
class DatasetSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def load_orders_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"orders dataset not found: {path}")
    frame = pd.read_csv(path)
    frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True)
    return frame.sort_values("created_at").reset_index(drop=True)


def filter_cod_orders(frame: pd.DataFrame) -> pd.DataFrame:
    cod_frame = frame.loc[frame["payment_method"] == "COD"].copy()
    if cod_frame.empty:
        raise ValueError("COD subset is empty")
    return cod_frame.sort_values("created_at").reset_index(drop=True)


def encode_target(frame: pd.DataFrame) -> pd.Series:
    valid_labels = {TARGET_POSITIVE_LABEL, TARGET_NEGATIVE_LABEL}
    labels = set(frame["rto_outcome"].dropna().unique())
    invalid = sorted(labels - valid_labels)
    if invalid:
        raise ValueError(f"invalid target labels: {invalid}")
    return frame["rto_outcome"].map({TARGET_POSITIVE_LABEL: 1, TARGET_NEGATIVE_LABEL: 0}).astype(int)


def temporal_split(frame: pd.DataFrame, train_fraction: float = 0.70, validation_fraction: float = 0.15) -> DatasetSplit:
    if not frame["created_at"].is_monotonic_increasing:
        frame = frame.sort_values("created_at").reset_index(drop=True)
    row_count = len(frame)
    if row_count < 10:
        raise ValueError("at least 10 rows are required for temporal splitting")

    train_end = int(row_count * train_fraction)
    validation_end = train_end + int(row_count * validation_fraction)
    if train_end == 0 or validation_end <= train_end or validation_end >= row_count:
        raise ValueError("invalid temporal split fractions for dataset size")

    return DatasetSplit(
        train=frame.iloc[:train_end].copy(),
        validation=frame.iloc[train_end:validation_end].copy(),
        test=frame.iloc[validation_end:].copy(),
    )


def split_boundaries(split: DatasetSplit) -> dict[str, str]:
    return {
        "train_start": split.train["created_at"].min().isoformat(),
        "train_end": split.train["created_at"].max().isoformat(),
        "validation_start": split.validation["created_at"].min().isoformat(),
        "validation_end": split.validation["created_at"].max().isoformat(),
        "test_start": split.test["created_at"].min().isoformat(),
        "test_end": split.test["created_at"].max().isoformat(),
    }

