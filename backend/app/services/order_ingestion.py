from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order, OrderStatus, PaymentMethod
from app.integrations.razorpay import RazorpayIdentifierMapping


def persist_razorpay_order(
    session: Session,
    internal_order_id: str,
    razorpay_order: dict[str, Any],
) -> tuple[Order, bool]:
    """Upsert one internal demo order and its external Test Mode metadata."""
    order = session.scalar(select(Order).where(Order.order_id == internal_order_id))
    created = order is None
    amount_paise = int(razorpay_order.get("amount") or 0)
    if order is None:
        order = Order(
            order_id=internal_order_id,
            customer_id=f"razorpay-test-{internal_order_id}",
            amount=Decimal(amount_paise) / Decimal("100"),
            payment_method=PaymentMethod.COD,
            order_status=OrderStatus.CREATED,
            customer_account_age_days=0,
            previous_cod_orders=0,
            previous_cod_refusals=0,
            previous_successful_deliveries=0,
            pincode="000000",
            product_category="unknown",
            is_first_order=True,
            source="razorpay_test",
            created_at=datetime.now(UTC),
        )
        session.add(order)

    # Never replace the internal amount on an existing record. The external
    # Test Mode amount is preserved only as Razorpay metadata.
    order.razorpay_order_id = razorpay_order.get("razorpay_order_id")
    order.external_receipt = razorpay_order.get("receipt")
    session.commit()
    session.refresh(order)
    return order, created


def attach_razorpay_mapping(session: Session, mapping: RazorpayIdentifierMapping) -> None:
    order = session.scalar(select(Order).where(Order.order_id == mapping.internal_order_id))
    if order is not None:
        order.razorpay_order_id = mapping.razorpay_order_id
        order.razorpay_payment_id = mapping.razorpay_payment_id
        order.external_receipt = mapping.receipt
        session.commit()
