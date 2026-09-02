from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str

    # App
    app_env: str = "development"
    secret_key: str
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    # Base URL for the links embedded in SMS. The default suits local development only —
    # a worker receiving a localhost link cannot open it, so _check_frontend_url below
    # refuses to start in production with this left unset.
    frontend_url: str = "http://localhost:5173"
    log_level: str = "INFO"  # Defaults to INFO; can be DEBUG, INFO, WARNING, ERROR

    # Concurrency / connection pool (see core/concurrency.py and core/supabase.py).
    # The request thread pool must stay <= db_max_connections so every concurrently running
    # handler can acquire a Supabase connection without hitting the pool timeout. The gap between
    # the two reserves connections for the background reminder job (runs on its own thread).
    db_max_connections: int = 24
    db_max_keepalive_connections: int = 12
    db_pool_timeout: float = 10.0
    request_thread_pool_size: int = 20

    # Bulk CSV worker import (see service/workers/service.py). The uploaded file is read fully into
    # memory and parsed synchronously on a request thread, so both bounds are needed to keep a
    # mis-selected file from occupying a worker thread indefinitely.
    max_import_file_bytes: int = 2_000_000
    max_import_rows: int = 1_000

    # Country code applied to phone numbers entered without one, e.g. "4165550101" -> "+14165550101".
    default_phone_country_code: str = "+1"

    # Reminder scheduling (see service/reminders/service.py). Two jobs run on the background
    # scheduler: the pre-service reminder sweep once a day, and the "you have been scheduled"
    # notice frequently enough to feel immediate without polling hard. The notice interval is the
    # worst-case delay between a schedule being created and its workers hearing about it.
    reminder_hour: int = Field(default=8, ge=0, le=23)
    notice_interval_minutes: int = Field(default=10, ge=1, le=1440)

    # How long a worker's confirmation link stays valid. This has to outlast the gap between the
    # two messages — a month's rota is generated weeks before its reminders fire, and the same
    # token backs both — so it is measured in days, not hours.
    confirmation_token_ttl_days: int = Field(default=45, ge=1)

    @model_validator(mode="after")
    def _check_pool_sizes(self) -> "Settings":
        """Fail fast if the request thread pool would outsize the DB connection pool.

        Raises:
            ValueError: If request_thread_pool_size exceeds db_max_connections.
        """
        if self.request_thread_pool_size > self.db_max_connections:
            raise ValueError(
                "request_thread_pool_size must be <= db_max_connections "
                f"(got {self.request_thread_pool_size} > {self.db_max_connections})"
            )
        return self

    @model_validator(mode="after")
    def _check_frontend_url(self) -> "Settings":
        """Fail fast if production would send SMS links nobody outside the server can open.

        This is the one setting whose misconfiguration is invisible from inside the app: the
        request succeeds, Twilio accepts the message, and the failure surfaces only when a worker
        taps a dead link. Note it can only fire when APP_ENV is actually set to "production".

        Raises:
            ValueError: If frontend_url is missing a scheme, or still points at localhost in
                production.
        """
        if not self.frontend_url.startswith(("http://", "https://")):
            raise ValueError(f"frontend_url must include a scheme, e.g. https://... (got {self.frontend_url!r})")
        if self.is_production and ("localhost" in self.frontend_url or "127.0.0.1" in self.frontend_url):
            raise ValueError(
                "frontend_url still points at localhost in production — set FRONTEND_URL to the "
                "public address of the app, or every SMS link will be unopenable"
            )
        return self

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production environment.

        Returns:
            bool: True if app_env is 'production', False otherwise.
        """
        return self.app_env == "production"


settings = Settings()  # type: ignore[call-arg]
