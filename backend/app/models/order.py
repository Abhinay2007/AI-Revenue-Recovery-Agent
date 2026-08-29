import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentMethod(str, enum.Enum):
    COD = "COD"
    PREPAID = "PREPAID"


class OrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    RTO = "RTO"
    CANCELLED = "CANCELLED"


class OrderOutcome(str, enum.Enum):
    RTO = "RTO"
    DELIVERED = "DELIVERED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    order_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False)
    customer_account_age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_cod_orders: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_cod_refusals: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_successful_deliveries: Mapped[int] = mapped_column(Integer, nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), index=True, nullable=False)
    product_category: Mapped[str] = mapped_column(String(64), nullable=False)
    is_first_order: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rto_outcome: Mapped[OrderOutcome | None] = mapped_column(Enum(OrderOutcome), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

