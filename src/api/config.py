"""Configuration module for GeoReforge.

This module contains the configuration settings for the GeoReforge application.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, AnyUrl

class Settings(BaseSettings):
    """Settings for the GeoReforge application."""
    flask_env: str = Field(default="production")
    debug: bool = Field(default=False)
    secret_key: str = Field(default="default_secret_key")
    database_url: AnyUrl | str = Field(default="/var/lib/app/database.db")
    log_level: str = Field(default="info")

    class Config:
        """Pydantic configuration for the settings."""
        env_file = "/etc/app/env.conf"
        env_file_encoding = "utf-8"
        case_sensitive = False
