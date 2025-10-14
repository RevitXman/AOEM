from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    APP_NAME: str = "S77 Discord Requests"
    SECRET_KEY: str = os.getenv("S77_SECRET_KEY", "d29yZHZpZXdzZWF0aGVhcHByb3ByaWF0ZWRyb3BwZWRkaWdmYXN0c2ltcGx5bnVtZXI")
    DB_URL: str = os.getenv("S77_DB_URL", "postgresql+psycopg2://s77:twnNPTkxg2ydrpau@localhost:5432/s77")
    BIND_HOST: str = os.getenv("S77_BIND_HOST", "192.168.15.71")
    BIND_PORT: int = int(os.getenv("S77_BIND_PORT", "8000"))
    ENV: str = os.getenv("S77_ENV", "prod")
    SHARED_JSON: str = os.getenv("S77_SHARED_JSON", "/opt/s77/shared/buff_requests.json")
    LOG_FILE: str = os.getenv("S77_LOG_FILE", "/opt/s77/logs/app.log")
    DEFAULT_LANG: str = os.getenv("S77_DEFAULT_LANG", "en")

settings = Settings()
