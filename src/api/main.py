"""Main API module for GeoReforge.

This module contains the primary API endpoints and configurations for the GeoReforge application.

.. functions::
    - `create_app`: Create and configure the Flask application.
    - `health_check`: Health check endpoint.
    - `enforce_secure_connection`: Enforces HTTPS connections based on the settings.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

from flask import Flask, Response, jsonify, request
from flask_wtf.csrf import CSRFError, CSRFProtect

from auth.manager import AuthManager
from auth.routes import auth_bp
from .config import DatabaseConfig, DatabaseSettings, FlaskSettings
from .web.routes import web_bp

def create_app(settings: FlaskSettings, database: DatabaseConfig | None = None) -> Flask:
    """Create and configure the Flask application.
    
    :param settings: Flask application settings.
    :type settings: FlaskSettings
    :param database: Database configuration, optional.
    :type database: DatabaseConfig | None
    :return: Configured Flask application.
    :rtype: Flask
    """
    __app: Flask = Flask(__name__)
    __app.config.from_mapping(settings.model_dump())
    CSRFProtect(__app)
    if database is None:
        database = DatabaseConfig(DatabaseSettings())
    __app.extensions["georeforge_database"] = database
    __app.extensions["auth_manager"] = AuthManager(__app, database.session, settings)
    __app.register_blueprint(auth_bp)
    __app.register_blueprint(web_bp)

    @__app.errorhandler(CSRFError)
    def handle_csrf_error(_error: CSRFError) -> tuple[Response, int]:
        return jsonify(error="CSRF validation failed"), 400

    @__app.errorhandler(401)
    def handle_unauthorized(_error: Exception) -> tuple[Response, int]:
        return jsonify(error="Authentication required"), 401

    @__app.errorhandler(403)
    def handle_forbidden(_error: Exception) -> tuple[Response, int]:
        return jsonify(error="Access forbidden"), 403

    @__app.before_request
    def enforce_secure_connection() -> Response | None:
        if (
            settings.ENFORCE_SECURE_CONNECTION
            and request.path != "/health"
            and not request.is_secure
        ):
            response = jsonify(error="Une connexion HTTPS est requise")
            response.status_code = 403
            return response
        return None

    @__app.after_request
    def prevent_authentication_caching(response: Response) -> Response:
        if request.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @__app.teardown_appcontext
    def remove_db_session(_exception: BaseException | None) -> None:
        """Remove the database session at the end of the request context.
        
        :param _exception: Exception raised during the request context, if any.
        :type _exception: BaseException | None
        :return: None
        :rtype: None
        """
        database.session.remove()

    __app.add_url_rule("/health", view_func=health_check)
    return __app

def health_check() -> dict[str, str]:
    """Health check endpoint.
    
    :return: Health status.
    :rtype: dict[str, str]
    """
    return {"status": "ok"}

app = create_app(FlaskSettings())
