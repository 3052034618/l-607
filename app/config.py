from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-change-in-production-please-use-a-very-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    DATABASE_URL: str = "sqlite:///./construction_waste.db"

    TRANSPORT_COST_PER_CUBIC_PER_KM: float = 2.5
    DISPOSAL_COST_PER_CUBIC: float = 15.0
    MAX_LOAD_WEIGHT: float = 25.0
    MAX_TRANSPORT_HOURS: float = 4.0
    OFF_ROUTE_THRESHOLD_METERS: float = 500.0

    CREDIT_SCORE_INITIAL: float = 100.0
    CREDIT_DEDUCTION_MINOR: float = 2.0
    CREDIT_DEDUCTION_MEDIUM: float = 5.0
    CREDIT_DEDUCTION_MAJOR: float = 10.0
    CREDIT_DEDUCTION_CRITICAL: float = 20.0

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
