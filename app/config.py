# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    DATABASE_SERVER: str
    DATABASE_NAME: str
    DATABASE_UID: str
    DATABASE_PWD: str

    # Add JWT settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

settings = Settings()

def get_connection_string():
    # 根据您的 SQL Server ODBC 驱动版本和操作系统调整
    # Windows: DRIVER={ODBC Driver 17 for SQL Server};
    # Linux:   DRIVER={ODBC Driver 17 for SQL Server};
    return (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={settings.DATABASE_SERVER};"
        f"DATABASE={settings.DATABASE_NAME};"
        f"UID={settings.DATABASE_UID};"
        f"PWD={settings.DATABASE_PWD}"
    ) 