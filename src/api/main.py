"""Main API module for GeoReforge.

This module contains the primary API endpoints and configurations for the GeoReforge application.
"""
from flask import Flask
from flask_wtf.csrf import CSRFProtect

from .config import Settings

def create_app(settings: Settings):
    """Create and configure the Flask application."""
    __app: Flask = Flask(__name__)
    __app.config.from_mapping(settings.model_dump())
    CSRFProtect(__app)
    return __app

app = create_app(Settings())

@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
