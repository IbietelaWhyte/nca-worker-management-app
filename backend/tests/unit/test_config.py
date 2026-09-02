import pytest
from pydantic import ValidationError

from app.core.config import Settings


class TestFrontendUrlInvariant:
    """frontend_url is the one setting whose misconfiguration is invisible from inside the app:
    the request succeeds, Twilio accepts the message, and the failure only surfaces when a worker
    taps a link pointing at the server's own localhost."""

    def test_rejects_localhost_in_production(self):
        # Other required fields come from the environment; only the two under test are overridden.
        with pytest.raises(ValidationError, match="localhost"):
            Settings(app_env="production", frontend_url="http://localhost:5173")

    def test_rejects_loopback_ip_in_production(self):
        with pytest.raises(ValidationError, match="localhost"):
            Settings(app_env="production", frontend_url="http://127.0.0.1:5173")

    def test_allows_localhost_outside_production(self):
        # The default has to keep working for local development.
        assert Settings(app_env="development", frontend_url="http://localhost:5173")

    def test_accepts_a_real_url_in_production(self):
        assert Settings(app_env="production", frontend_url="https://rota.example.org")

    @pytest.mark.parametrize("value", ["rota.example.org", "//rota.example.org", ""])
    def test_rejects_a_url_with_no_scheme(self, value):
        # "rota.example.org/confirm/<uuid>" is not a link anything will open.
        with pytest.raises(ValidationError, match="scheme"):
            Settings(frontend_url=value)
