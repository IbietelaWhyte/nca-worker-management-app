from app.core.config import settings
from tests.integration.routers.conftest import make_client


def test_api_responses_carry_the_security_headers():
    response = make_client().get("/api/v1/availability/config")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    # Responses carry people's contact details; nothing should keep them in a shared cache.
    assert response.headers["Cache-Control"] == "no-store"


def test_cors_allows_what_the_spa_sends():
    response = make_client().options(
        "/api/v1/workers",
        headers={
            "Origin": settings.allowed_origins[0],
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == settings.allowed_origins[0]
    # Bearer tokens, not cookies: there are no credentials for the browser to send.
    assert "access-control-allow-credentials" not in response.headers


def test_cors_refuses_headers_the_spa_does_not_send():
    response = make_client().options(
        "/api/v1/workers",
        headers={
            "Origin": settings.allowed_origins[0],
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-something-else",
        },
    )

    assert response.status_code == 400
