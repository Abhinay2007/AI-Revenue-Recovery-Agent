def test_health_returns_ok(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    from app.main import app

    health_route = next(route for route in app.routes if getattr(route, "path", None) == "/health")
    response = health_route.endpoint()

    assert "GET" in health_route.methods
    assert response == {"status": "ok"}
