import pytest

from data.generate import generate_orders, validate_orders


def test_validation_accepts_valid_records():
    records = generate_orders(rows=500, seed=11)

    validate_orders(records)


def test_validation_rejects_negative_amount():
    records = generate_orders(rows=500, seed=11)
    records[0]["amount"] = "-1.00"

    with pytest.raises(ValueError, match="negative amount"):
        validate_orders(records)


def test_validation_rejects_invalid_payment_method():
    records = generate_orders(rows=500, seed=11)
    records[0]["payment_method"] = "CARD_ON_DELIVERY"

    with pytest.raises(ValueError, match="invalid payment_method"):
        validate_orders(records)


def test_validation_rejects_duplicate_order_ids():
    records = generate_orders(rows=500, seed=11)
    records[1]["order_id"] = records[0]["order_id"]

    with pytest.raises(ValueError, match="duplicate order_id"):
        validate_orders(records)


def test_validation_rejects_single_outcome_dataset():
    records = generate_orders(rows=500, seed=11)
    for record in records:
        record["rto_outcome"] = "DELIVERED"

    with pytest.raises(ValueError, match="both RTO and DELIVERED"):
        validate_orders(records)

