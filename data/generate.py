from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = [
    "order_id",
    "customer_id",
    "amount",
    "payment_method",
    "order_status",
    "customer_account_age_days",
    "previous_cod_orders",
    "previous_cod_refusals",
    "previous_successful_deliveries",
    "pincode",
    "pincode_risk_group",
    "pincode_rto_rate",
    "product_category",
    "is_first_order",
    "created_at",
    "rto_outcome",
]

PAYMENT_METHODS = {"COD", "PREPAID"}
RTO_OUTCOMES = {"RTO", "DELIVERED"}
ORDER_STATUSES = {"DELIVERED", "RTO"}
PRODUCT_CATEGORY_EFFECTS = {
    "apparel": 0.09,
    "footwear": 0.07,
    "beauty": 0.01,
    "electronics": 0.04,
    "home": -0.02,
    "grocery": -0.05,
    "jewellery": 0.05,
}
PINCODE_GROUPS = {
    "LOW": (0.08, 0.16),
    "MEDIUM": (0.17, 0.29),
    "HIGH": (0.30, 0.45),
}


@dataclass(frozen=True)
class PincodeProfile:
    pincode: str
    risk_group: str
    rto_rate: float


def sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def create_pincode_profiles(seed: int, count: int = 240) -> list[PincodeProfile]:
    rng = random.Random(seed + 17)
    profiles: list[PincodeProfile] = []
    for index in range(count):
        pincode = f"{110000 + index:06d}"
        bucket_roll = rng.random()
        if bucket_roll < 0.25:
            group = "HIGH"
        elif bucket_roll < 0.65:
            group = "MEDIUM"
        else:
            group = "LOW"
        low, high = PINCODE_GROUPS[group]
        profiles.append(PincodeProfile(pincode, group, round(rng.uniform(low, high), 4)))
    return profiles


def weighted_choice(rng: random.Random, values: list[tuple[str, float]]) -> str:
    total = sum(weight for _, weight in values)
    marker = rng.uniform(0, total)
    cumulative = 0.0
    for value, weight in values:
        cumulative += weight
        if marker <= cumulative:
            return value
    return values[-1][0]


def generate_orders(rows: int, seed: int | None = None) -> list[dict[str, Any]]:
    if rows <= 0:
        raise ValueError("rows must be greater than zero")

    rng = random.Random(seed)
    profiles = create_pincode_profiles(seed or 0)
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    orders: list[dict[str, Any]] = []

    for index in range(rows):
        is_first_order = rng.random() < 0.28
        account_age = rng.randint(0, 35) if is_first_order else rng.randint(20, 1600)
        previous_successes = 0 if is_first_order else min(rng.randint(0, 18), int(account_age / 35) + rng.randint(0, 4))
        previous_cod_orders = 0 if is_first_order else previous_successes + rng.randint(0, 6)
        previous_refusals = 0 if previous_cod_orders == 0 else min(previous_cod_orders, rng.choices([0, 1, 2, 3, 4], [58, 24, 11, 5, 2])[0])

        payment_method = weighted_choice(rng, [("COD", 0.72), ("PREPAID", 0.28)])
        category = weighted_choice(
            rng,
            [
                ("apparel", 0.23),
                ("footwear", 0.13),
                ("beauty", 0.14),
                ("electronics", 0.12),
                ("home", 0.17),
                ("grocery", 0.13),
                ("jewellery", 0.08),
            ],
        )
        profile = rng.choice(profiles)

        amount = round(rng.lognormvariate(math.log(1450), 0.65), 2)
        amount = max(149.0, min(amount, 24999.0))

        risk_score = -1.65
        risk_score += 0.95 if payment_method == "COD" else -0.55
        risk_score += (profile.rto_rate - 0.22) * 3.1
        risk_score += PRODUCT_CATEGORY_EFFECTS[category] * 2.0
        risk_score += min(previous_refusals, 4) * 0.42
        risk_score -= min(previous_successes, 12) * 0.12
        risk_score += 0.24 if is_first_order else 0.0
        risk_score += 0.28 if amount > 5000 else 0.0
        risk_score += rng.normalvariate(0, 0.38)

        rto_probability = min(max(sigmoid(risk_score), 0.03), 0.82)
        rto_outcome = "RTO" if rng.random() < rto_probability else "DELIVERED"

        created_at = base_time + timedelta(minutes=index * 7)
        orders.append(
            {
                "order_id": f"ORD-{seed or 0:04d}-{index + 1:07d}",
                "customer_id": f"CUST-{rng.randint(1, max(250, rows // 3)):07d}",
                "amount": f"{amount:.2f}",
                "payment_method": payment_method,
                "order_status": rto_outcome,
                "customer_account_age_days": account_age,
                "previous_cod_orders": previous_cod_orders,
                "previous_cod_refusals": previous_refusals,
                "previous_successful_deliveries": previous_successes,
                "pincode": profile.pincode,
                "pincode_risk_group": profile.risk_group,
                "pincode_rto_rate": f"{profile.rto_rate:.4f}",
                "product_category": category,
                "is_first_order": is_first_order,
                "created_at": created_at.isoformat(),
                "rto_outcome": rto_outcome,
            }
        )

    return orders


def validate_orders(records: list[dict[str, Any]]) -> None:
    if not records:
        raise ValueError("dataset must contain at least one record")

    missing = set(REQUIRED_COLUMNS) - set(records[0].keys())
    if missing:
        raise ValueError(f"dataset is missing required columns: {sorted(missing)}")

    order_ids: set[str] = set()
    outcomes: set[str] = set()

    for row_number, record in enumerate(records, start=1):
        order_id = str(record["order_id"])
        if order_id in order_ids:
            raise ValueError(f"duplicate order_id at row {row_number}: {order_id}")
        order_ids.add(order_id)

        amount = float(record["amount"])
        if amount < 0:
            raise ValueError(f"negative amount at row {row_number}")

        payment_method = str(record["payment_method"])
        if payment_method not in PAYMENT_METHODS:
            raise ValueError(f"invalid payment_method at row {row_number}: {payment_method}")

        order_status = str(record["order_status"])
        if order_status not in ORDER_STATUSES:
            raise ValueError(f"invalid order_status at row {row_number}: {order_status}")

        outcome = str(record["rto_outcome"])
        if outcome not in RTO_OUTCOMES:
            raise ValueError(f"invalid rto_outcome at row {row_number}: {outcome}")
        outcomes.add(outcome)

        account_age = int(record["customer_account_age_days"])
        if account_age < 0 or account_age > 5000:
            raise ValueError(f"unreasonable customer_account_age_days at row {row_number}")

        for column in ["previous_cod_orders", "previous_cod_refusals", "previous_successful_deliveries"]:
            value = int(record[column])
            if value < 0 or value > 250:
                raise ValueError(f"unreasonable {column} at row {row_number}")

        if int(record["previous_cod_refusals"]) > int(record["previous_cod_orders"]):
            raise ValueError(f"previous refusals exceed previous COD orders at row {row_number}")

        pincode_rate = float(record["pincode_rto_rate"])
        if pincode_rate < 0 or pincode_rate > 1:
            raise ValueError(f"invalid pincode_rto_rate at row {row_number}")

    if outcomes != RTO_OUTCOMES:
        raise ValueError("dataset must contain both RTO and DELIVERED outcomes")


def write_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(records)


def read_csv(input_path: Path) -> list[dict[str, str]]:
    with input_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic D2C order data.")
    parser.add_argument("--rows", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path("data/generated/orders.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = generate_orders(rows=args.rows, seed=args.seed)
    validate_orders(records)
    write_csv(records, args.output)
    print(f"generated {len(records)} rows at {args.output}")


if __name__ == "__main__":
    main()

