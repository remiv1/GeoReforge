"""Configuration module for GeoReforge.

This module contains the configuration settings for the GeoReforge application.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """Settings for the GeoReforge application."""
    model_config = SettingsConfigDict(
        env_file="/etc/app/env.conf",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    FLASK_ENV: str = Field(default="production")
    DEBUG: bool = Field(default=False, validation_alias="flask_debug")
    SECRET_KEY: str = Field(default="default_secret_key")
    LOG_LEVEL: str = Field(default="info")
