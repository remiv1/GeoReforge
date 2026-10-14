"""Configuration module for GeoReforge.

This module contains the configuration settings for the GeoReforge application.

.. classes::
    - `Settings`: Contains the configuration settings for the GeoReforge application.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

import logging

from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

LOGGER = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Settings for the GeoReforge application.
    
    :param model_config: The configuration for the Pydantic model.
    :type model_config: SettingsConfigDict
    :param FLASK_ENV: The Flask environment (e.g., "production" or "development").
    :type FLASK_ENV: str
    :param DEBUG: Whether to enable Flask debug mode.
    :type DEBUG: bool
    :param SECRET_KEY: The secret key for the Flask application.
    :type SECRET_KEY: str
    :param LOG_LEVEL: The logging level for the application.
    :type LOG_LEVEL: str
    :param AUTH_MODE: The authentication mode ("none", "internal", or "external").
    :type AUTH_MODE: Literal["none", "internal", "external"]
    :param ADMIN_USERNAME: The username for the initial administrator (internal mode).
    :type ADMIN_USERNAME: str
    :param ADMIN_PASSWORD: The password for the initial administrator (internal mode).
    :type ADMIN_PASSWORD: str
    :param OIDC_ISSUER: The OIDC issuer URL (external mode).
    :type OIDC_ISSUER: str
    :param OIDC_CLIENT_ID: The OIDC client ID (external mode).
    :type OIDC_CLIENT_ID: str
    :param OIDC_CLIENT_SECRET: The OIDC client secret (external mode).
    :type OIDC_CLIENT_SECRET: str
    :param OIDC_REDIRECT_URI: The OIDC redirect URI (external mode).
    :type OIDC_REDIRECT_URI: str
    :param AUTH_COOKIE_NAME: The name of the authentication cookie.
    :type AUTH_COOKIE_NAME: str
    :param AUTH_COOKIE_SECURE: Whether the authentication cookie should be secure.
    :type AUTH_COOKIE_SECURE: bool

    .. methods::
        - `validate_authentication`: Validates the authentication-related settings based
        on the chosen authentication mode.

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """
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
    AUTH_MODE: Literal["none", "internal", "external"] = "none"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = Field(default="", repr=False)
    OIDC_ISSUER: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = Field(default="", repr=False)
    OIDC_REDIRECT_URI: str = ""
    AUTH_COOKIE_NAME: str = "georeforge_session"
    AUTH_COOKIE_SECURE: bool = False

    @model_validator(mode="after")
    def validate_authentication(self):
        """Validate the necessary secrets for the chosen authentication mode.
        
        :return: The validated settings instance.
        :rtype: Self

        :raises ValueError: If the authentication-related settings are invalid.
        """
        if self.AUTH_MODE == "none":
            LOGGER.debug("Authentication mode is set to 'none'")
            return self
        if self.SECRET_KEY == "default_secret_key":
            LOGGER.exception("SECRET_KEY is set to the default value")
            raise ValueError("SECRET_KEY doit etre personnalise hors du mode none")
        if self.AUTH_MODE == "internal" and not self.ADMIN_PASSWORD:
            LOGGER.exception("ADMIN_PASSWORD is not set in internal authentication mode")
            raise ValueError("ADMIN_PASSWORD doit etre defini en mode internal")
        if self.AUTH_MODE == "external":
            required = (
                self.OIDC_ISSUER,
                self.OIDC_CLIENT_ID,
                self.OIDC_CLIENT_SECRET,
                self.OIDC_REDIRECT_URI,
            )
            if not all(required):
                absent = [
                    name for name in [
                        "OIDC_ISSUER",
                        "OIDC_CLIENT_ID",
                        "OIDC_CLIENT_SECRET",
                        "OIDC_REDIRECT_URI",
                    ] if name not in required
                ]
                if absent:
                    LOGGER.exception(
                        "OIDC configuration is incomplete: missing %s",
                        ", ".join(absent)
                    )
                raise ValueError("La configuration OIDC est incomplete")
            if urlparse(self.OIDC_REDIRECT_URI).path != "/auth/callback":
                LOGGER.exception(
                    "OIDC_REDIRECT_URI must point to /auth/callback, but got %s",
                    self.OIDC_REDIRECT_URI
                )
                raise ValueError("OIDC_REDIRECT_URI doit pointer vers /auth/callback")
        return self
