from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.models import order  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _add_order_metadata_columns()


def _add_order_metadata_columns() -> None:
    """Add the small ingestion fields for databases created before this milestone."""
    columns = {column["name"] for column in inspect(engine).get_columns("orders")}
    additions = {
        "source": "VARCHAR(32) DEFAULT 'synthetic' NOT NULL",
        "razorpay_order_id": "VARCHAR(64)",
        "razorpay_payment_id": "VARCHAR(64)",
        "external_receipt": "VARCHAR(40)",
    }
    missing = {name: definition for name, definition in additions.items() if name not in columns}
    if not missing:
        return
    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE orders ADD COLUMN {name} {definition}"))
