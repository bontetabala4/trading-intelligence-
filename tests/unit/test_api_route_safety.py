"""The public application must not expose fixture or order-execution routes."""
from apps.api.main import create_app


def test_only_the_canonical_versioned_decision_route_is_public():
    app = create_app()
    routes = {route.path for route in app.routes}

    assert "/api/v1/decision/{symbol}" in routes
    assert "/api/v1/decisions/{symbol}" in routes
    assert "/signals/{symbol}" not in routes
    assert "/risk/evaluate" not in routes
    assert "/regime/{symbol}" not in routes
    assert "/execution/execute" not in routes
