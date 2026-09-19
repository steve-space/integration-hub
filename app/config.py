from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Where the two backend ("System API") targets live, and how long we
    wait before treating one of them as down."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    warehouse_system_url: str = "http://localhost:9001"
    pricing_system_url: str = "http://localhost:9002"
    backend_timeout_seconds: float = 5.0


settings = Settings()
