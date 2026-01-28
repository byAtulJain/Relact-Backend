from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_days: int = 7
    encryption_key: str
    firebase_credentials_path: str = "./firebase-service-account.json"
    
    # Email Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_from_name: str = "Relact - Smart Contact Manager"
    
    class Config:
        env_file = ".env"
        extra = "allow"  # Allow extra fields from .env


@lru_cache()
def get_settings():
    return Settings()
