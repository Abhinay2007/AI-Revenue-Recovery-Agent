from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.order import Order
from app.services.health import check_database_health


def test_database_health_check_uses_sqlalchemy_connection():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    with Session(engine) as session:
        assert check_database_health(session) is True


def test_orders_model_metadata_can_create_table():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(bind=engine)

    assert Order.__tablename__ in Base.metadata.tables

