"""Configuration package for the GeoReforge API."""
from .c_flask import Settings as FlaskSettings
from .c_databases import Settings as DatabaseSettings

__all__ = ["FlaskSettings", "DatabaseSettings"]
