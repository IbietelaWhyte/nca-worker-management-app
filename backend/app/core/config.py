from pydantic import model_validator
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

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production environment.

        Returns:
            bool: True if app_env is 'production', False otherwise.
        """
        return self.app_env == "production"


settings = Settings()  # type: ignore[call-arg]
