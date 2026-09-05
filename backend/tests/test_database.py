from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.order import Order
from app.services.health import check_database_health
from app.core.config import normalize_database_url


def test_database_health_check_uses_sqlalchemy_connection():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    with Session(engine) as session:
        assert check_database_health(session) is True


def test_orders_model_metadata_can_create_table():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(bind=engine)

    assert Order.__tablename__ in Base.metadata.tables


def test_unqualified_postgresql_url_uses_psycopg_v3():
    normalized = normalize_database_url("postgresql://user:password@localhost:5432/db?sslmode=require")

    assert normalized.startswith("postgresql+psycopg://")
    assert "localhost:5432/db" in normalized
    assert "sslmode=require" in normalized


def test_sqlite_url_is_unchanged():
    url = "sqlite+pysqlite:///:memory:"

    assert normalize_database_url(url) == url
