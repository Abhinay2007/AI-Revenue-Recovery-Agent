def test_health_returns_ok(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    from app.main import app

    health_route = next(route for route in app.routes if getattr(route, "path", None) == "/health")
    response = health_route.endpoint()

    assert "GET" in health_route.methods
    assert response == {"status": "ok"}


def test_recovery_decision_endpoint_returns_deterministic_recommendation():
    from app.api.routes.recovery import create_recovery_decision
    from app.schemas.recovery import RecoveryDecisionRequest

    response = create_recovery_decision(
        RecoveryDecisionRequest(
            order_id="ORD-0042-0009773",
            amount=7033.69,
            rto_probability=0.46159831875238705,
        )
    )

    assert response["recommended_action"] == "PREPAID_INCENTIVE"
    assert response["expected_revenue_at_risk"] == 3246.74
    assert response["expected_net_recovery"] == 860.52
