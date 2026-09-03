import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def disable_real_razorpay_during_tests(monkeypatch):
    monkeypatch.setenv("RAZORPAY_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
