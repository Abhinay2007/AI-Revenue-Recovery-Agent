from pathlib import Path

import pytest

from app.core.config import Settings, get_default_dataset_path
from app.ml.data import load_orders_csv


def test_default_dataset_path_is_repo_relative():
    repo_root = Path(__file__).resolve().parents[2]
    expected = repo_root / "data" / "generated" / "orders.csv"

    assert get_default_dataset_path() == expected


def test_dataset_path_env_override_is_used(monkeypatch):
    override = "/tmp/custom-orders.csv"
    monkeypatch.setenv("DATASET_PATH", override)

    assert get_default_dataset_path() == Path(override)
    assert Settings().dataset_path == Path(override)


def test_missing_dataset_raises_clear_error():
    missing_path = Path("/tmp/definitely-missing-orders-file.csv")

    with pytest.raises(FileNotFoundError, match=r"orders dataset not found: .*definitely-missing-orders-file\.csv"):
        load_orders_csv(missing_path)


def test_default_dataset_path_is_cwd_independent(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    expected = repo_root / "data" / "generated" / "orders.csv"

    monkeypatch.chdir(tmp_path)
    assert get_default_dataset_path() == expected

    monkeypatch.chdir(repo_root / "backend")
    assert get_default_dataset_path() == expected
