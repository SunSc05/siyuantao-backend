# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pydantic import EmailStr, HttpUrl, Field, validator # Import necessary types and Field, validator
from typing import Optional # Import Optional
from pydantic import model_validator

class Settings(BaseSettings):
    DATABASE_SERVER: str
    DATABASE_NAME: str
    DATABASE_UID: str
    DATABASE_PWD: str

    # Add JWT settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Email Service Provider Selection
    # Use "smtp" or "aliyun"
    EMAIL_PROVIDER: str = Field(..., description="邮件服务提供商: smtp 或 aliyun") # Make this required

    # SMTP Settings (Optional if Aliyun is used)
    SMTP_SERVER: Optional[str] = Field(None, description="SMTP 服务器地址") # Make optional
    SMTP_PORT: Optional[int] = Field(None, description="SMTP 服务器端口") # Make optional
    SMTP_USERNAME: Optional[str] = Field(None, description="SMTP 用户名") # Make optional
    SMTP_PASSWORD: Optional[str] = Field(None, description="SMTP 密码") # Make optional

    # Aliyun Direct Mail Settings (Optional if SMTP is used)
    ALIYUN_EMAIL_ACCESS_KEY_ID: Optional[str] = Field(None, description="阿里云邮件服务 Access Key ID") # Uncomment and make optional
    ALIYUN_EMAIL_ACCESS_KEY_SECRET: Optional[str] = Field(None, description="阿里云邮件服务 Access Key Secret") # Uncomment and make optional
    ALIYUN_EMAIL_REGION: str = Field("cn-hangzhou", description="阿里云邮件服务区域") # Uncomment

    SENDER_EMAIL: EmailStr = Field(..., description="发件人邮箱地址") # Keep required

    # Frontend Domain for Magic Link
    FRONTEND_DOMAIN: HttpUrl = Field("http://localhost:3301", description="前端域名") # Keep required

    # Magic Link Expiration
    MAGIC_LINK_EXPIRE_MINUTES: int = 15 # 魔术链接过期时间（分钟）

    @validator('EMAIL_PROVIDER')
    def validate_email_provider(cls, v):
        if v not in ('smtp', 'aliyun'):
            raise ValueError('EMAIL_PROVIDER 必须是 "smtp" 或 "aliyun"')
        return v

    # Use model_validator for cross-field validation in Pydantic v2
    @model_validator(mode='after')
    def check_email_provider_settings(self):
        if self.EMAIL_PROVIDER == 'smtp':
            missing_fields = []
            if self.SMTP_SERVER is None: missing_fields.append('SMTP_SERVER')
            if self.SMTP_PORT is None: missing_fields.append('SMTP_PORT')
            if self.SMTP_USERNAME is None: missing_fields.append('SMTP_USERNAME')
            if self.SMTP_PASSWORD is None: missing_fields.append('SMTP_PASSWORD')
            if missing_fields:
                raise ValueError(f"当 EMAIL_PROVIDER 为 'smtp' 时，以下字段必须设置: {', '.join(missing_fields)}")

        elif self.EMAIL_PROVIDER == 'aliyun':
             missing_fields = []
             if self.ALIYUN_EMAIL_ACCESS_KEY_ID is None: missing_fields.append('ALIYUN_EMAIL_ACCESS_KEY_ID')
             if self.ALIYUN_EMAIL_ACCESS_KEY_SECRET is None: missing_fields.append('ALIYUN_EMAIL_ACCESS_KEY_SECRET')
             if missing_fields:
                 raise ValueError(f"当 EMAIL_PROVIDER 为 'aliyun' 时，以下字段必须设置: {', '.join(missing_fields)}")

        return self

    model_config = SettingsConfigDict(env_file='.env', extra='ignore') # Ensure .env is loaded

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