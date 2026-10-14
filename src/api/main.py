"""Main API module for GeoReforge.

This module contains the primary API endpoints and configurations for the GeoReforge application.

.. functions::
    - `create_app`: Create and configure the Flask application.

.. routes::
    - `/health`: Health check endpoint.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from auth.manager import AuthManager
from auth.routes import auth_bp
from .config import DatabaseConfig, DatabaseSettings, FlaskSettings

def create_app(settings: FlaskSettings, database: DatabaseConfig | None = None) -> Flask:
    """Create and configure the Flask application.
    
    :param settings: Flask application settings.
    :type settings: FlaskSettings
    :param database: Database configuration, optional.
    :type database: DatabaseConfig | None
    :return: Configured Flask application.
    :rtype: Flask

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """
    __app: Flask = Flask(__name__)
    __app.config.from_mapping(settings.model_dump())
    CSRFProtect(__app)
    if database is None:
        database = DatabaseConfig(DatabaseSettings())
    __app.extensions["georeforge_database"] = database
    __app.extensions["auth_manager"] = AuthManager(__app, database.session, settings)
    __app.register_blueprint(auth_bp)

    @__app.teardown_appcontext
    def remove_db_session(_exception: BaseException | None) -> None:
        """Remove the database session at the end of the request context.
        
        :param _exception: Exception raised during the request context, if any.
        :type _exception: BaseException | None
        :return: None
        :rtype: None
        """
        database.session.remove()

    return __app

app = create_app(FlaskSettings())

@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint.
    
    :return: Health status.
    :rtype: dict[str, str]
    """
    return {"status": "ok"}
