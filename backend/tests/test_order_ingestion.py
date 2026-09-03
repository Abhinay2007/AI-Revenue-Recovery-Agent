from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.integrations.razorpay import DatabaseRazorpayMappingStore, RazorpayIdentifierMapping
from app.models.order import Order
from app.services.order_ingestion import persist_razorpay_order


def make_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def test_razorpay_order_and_mapping_persist_across_fresh_sessions():
    sessions = make_database()
    external = {
        "razorpay_order_id": "order_test_ingest",
        "amount": 100,
        "currency": "INR",
        "receipt": "rr_ingest",
        "status": "created",
    }

    with sessions() as session:
        order, created = persist_razorpay_order(session, "RZP-TEST-1", external)
        assert created is True
        assert order.source == "razorpay_test"
        assert order.amount == 1
        mapping_store = DatabaseRazorpayMappingStore(session_factory=sessions)
        mapping_store.save(RazorpayIdentifierMapping("RZP-TEST-1", "order_test_ingest", receipt="rr_ingest"))

    fresh_store = DatabaseRazorpayMappingStore(session_factory=sessions)
    mapping = fresh_store.get("RZP-TEST-1")
    with sessions() as session:
        stored_order = session.scalar(select(Order).where(Order.order_id == "RZP-TEST-1"))

    assert mapping is not None
    assert mapping.razorpay_order_id == "order_test_ingest"
    assert stored_order is not None
    assert stored_order.razorpay_order_id == "order_test_ingest"


def test_duplicate_ingestion_upserts_without_duplicate_internal_records():
    sessions = make_database()
    external = {"razorpay_order_id": "order_test_duplicate", "amount": 10000, "receipt": "rr_dup"}

    with sessions() as session:
        first, first_created = persist_razorpay_order(session, "RZP-TEST-DUP", external)
        second, second_created = persist_razorpay_order(
            session,
            "RZP-TEST-DUP",
            {**external, "amount": 99999, "razorpay_order_id": "order_test_duplicate"},
        )
        count = session.scalar(select(func.count()).select_from(Order).where(Order.order_id == "RZP-TEST-DUP"))

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert second.amount == 100
    assert count == 1
    assert second.source == "razorpay_test"
