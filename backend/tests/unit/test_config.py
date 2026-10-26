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
        # "rota.example.org/availability/<uuid>" is not a link anything will open.
        with pytest.raises(ValidationError, match="scheme"):
            Settings(frontend_url=value)


class TestSupabaseKeys:
    """Supabase accepts either generation of key, so a wrong one fails nowhere near where it was
    set: a legacy key on the day it is disabled, a swapped pair on every query."""

    SECRET = "sb_secret_abc"
    PUBLISHABLE = "sb_publishable_abc"

    def test_accepts_a_well_formed_pair(self):
        settings = Settings(supabase_secret_key=self.SECRET, supabase_publishable_key=self.PUBLISHABLE)
        assert settings.supabase_secret_key == self.SECRET

    def test_rejects_a_legacy_service_role_key(self):
        with pytest.raises(ValidationError, match="SUPABASE_SECRET_KEY.*legacy JWT"):
            Settings(supabase_secret_key="eyJhbGciOiJIUzI1NiJ9.x.y", supabase_publishable_key=self.PUBLISHABLE)

    def test_rejects_a_legacy_anon_key(self):
        with pytest.raises(ValidationError, match="SUPABASE_PUBLISHABLE_KEY.*legacy JWT"):
            Settings(supabase_secret_key=self.SECRET, supabase_publishable_key="eyJhbGciOiJIUzI1NiJ9.x.y")

    def test_rejects_a_swapped_pair(self):
        with pytest.raises(ValidationError, match="swapped"):
            Settings(supabase_secret_key=self.PUBLISHABLE, supabase_publishable_key=self.SECRET)

    def test_the_message_never_contains_the_key(self):
        with pytest.raises(ValidationError) as excinfo:
            Settings(supabase_secret_key="eyJsupersecretvalue", supabase_publishable_key=self.PUBLISHABLE)
        assert "supersecretvalue" not in str(excinfo.value)
