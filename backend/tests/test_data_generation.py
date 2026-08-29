from data.generate import REQUIRED_COLUMNS, generate_orders, validate_orders


def test_requested_row_count_is_respected():
    records = generate_orders(rows=125, seed=42)

    assert len(records) == 125


def test_seed_produces_reproducible_output():
    first = generate_orders(rows=25, seed=7)
    second = generate_orders(rows=25, seed=7)

    assert first == second


def test_required_columns_exist():
    records = generate_orders(rows=20, seed=42)

    assert set(REQUIRED_COLUMNS).issubset(records[0].keys())


def test_generated_dataset_has_both_outcomes():
    records = generate_orders(rows=500, seed=42)
    outcomes = {record["rto_outcome"] for record in records}

    assert outcomes == {"RTO", "DELIVERED"}


def test_generated_dataset_has_no_duplicate_order_ids():
    records = generate_orders(rows=500, seed=42)
    order_ids = [record["order_id"] for record in records]

    assert len(order_ids) == len(set(order_ids))


def test_generated_dataset_passes_validation():
    records = generate_orders(rows=500, seed=42)

    validate_orders(records)

