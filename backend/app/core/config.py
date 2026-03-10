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

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production environment.

        Returns:
            bool: True if app_env is 'production', False otherwise.
        """
        return self.app_env == "production"


settings = Settings()  # type: ignore[call-arg]
