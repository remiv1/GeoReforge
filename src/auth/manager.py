"""Central selection and orchestration of authentication backends.

.. classes::
    - `AuthManager`: Central selection and orchestration of authentication backends.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Literal

from flask import Flask, current_app
from sqlalchemy.orm import Session, scoped_session

from auth.backends.base import AuthBackend
from auth.backends.internal import InternalAuthBackend
from auth.backends.none import NoneAuthBackend
from auth.models import User
from auth.services import SessionService, UserService
from api.config import FlaskSettings

AuthMode = Literal["none", "internal", "external"]
LOGGER = logging.getLogger(__name__)

class AuthManager:
    """Give a configured backend to the application.
    This class is responsible for selecting and orchestrating the appropriate authentication backend
    based on the application's configuration.

    :param app: The Flask application instance.
    :type app: Flask
    :param db_session: The scoped session for database interactions.
    :type db_session: scoped_session[Session]
    :param settings: The Flask application settings containing authentication configuration.
    :type settings: FlaskSettings

    .. methods::
        - `authenticate`: Authenticates a user based on provided credentials.
        - `begin_login`: Initiates the login process by redirecting to the OIDC provider.
        - `complete_login`: Completes the login process and returns the authenticated user.
        - `get_current_user`: Retrieves the currently authenticated user based on the session token.
        - `logout`: Logs out the user by deleting the session token.

    .. author: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """

    def __init__(
        self,
        app: Flask,
        db_session: scoped_session[Session],
        settings: FlaskSettings,
    ) -> None:
        """Initializes the AuthManager with the given Flask application, database session,
        and settings.

        :param app: The Flask application instance.
        :type app: Flask
        :param db_session: The scoped session for database interactions.
        :type db_session: scoped_session[Session]
        :param settings: The Flask application settings containing authentication configuration.
        :type settings: FlaskSettings
        """
        self.app = app
        self.settings = settings
        self.mode: AuthMode = settings.AUTH_MODE
        self.sessions = SessionService(db_session)
        self.users = UserService(db_session)
        self.backend = self._create_backend()

    @classmethod
    def get_backend(cls) -> AuthBackend:
        """Returns the current backend without exposing its construction to the blueprints.
        
        :return: The current authentication backend.
        :rtype: AuthBackend
        """
        return current_app.extensions["auth_manager"].backend

    @classmethod
    def initialize_database(
        cls,
        db_session: scoped_session[Session],
        settings: FlaskSettings,
    ) -> None:
        """Creates the initial groups and administrator when necessary.

        :return: None
        :rtype: None
        """
        service = UserService(db_session)
        if settings.AUTH_MODE == "internal":
            service.ensure_initial_admin(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        elif settings.AUTH_MODE == "external":
            service.ensure_groups()

    def authenticate(
        self,
        credentials: dict[str, object] | None = None,
    ) -> tuple[User, str | None] | None:
        """Authenticates and creates a persistent session if the mode requires it.

        :param credentials: The credentials provided for authentication.
        :type credentials: dict[str, object] | None

        :return: A tuple containing the authenticated user and the session token,
        or None if authentication fails.
        :rtype: tuple[User, str | None] | None
        """
        user = self.backend.authenticate(credentials)
        if user is None:
            LOGGER.warning("Authentication failed for credentials: %s", credentials)
            return None
        token = self.sessions.create(int(user.id)) if self.mode != "none" else None
        return user, token

    def complete_login(self) -> tuple[User, str]:
        """Completes the OIDC login process and creates a GeoReforge session.

        :return: A tuple containing the authenticated user and the session token.
        :rtype: tuple[User, str]
        """
        user = self.backend.complete_login()
        return user, self.sessions.create(int(user.id))

    def get_current_user(self, session_token: str | None = None) -> User | None:
        """Retrieves the currently authenticated user via the chosen backend.

        :param session_token: The session token associated with the user's session.
        :type session_token: str | None

        :return: The currently authenticated user, or None if no user is associated
        with the session token.
        :rtype: User | None
        """
        return self.backend.get_current_user(session_token)

    def logout(self, session_token: str | None = None) -> None:
        """Logs out the current session.

        :param session_token: The session token associated with the user's session.
        :type session_token: str | None

        :return: None
        :rtype: None
        """
        self.backend.logout(session_token)

    def begin_login(self):
        """Initiates an interactive login flow when supported.

        :return: A Flask response object that redirects the user to the OIDC provider's login page.
        :rtype: Response
        """
        return self.backend.begin_login()

    def _create_backend(self) -> AuthBackend:
        if self.mode == "none":
            return NoneAuthBackend()
        if self.mode == "internal":
            return InternalAuthBackend(self.users, self.sessions)
        from auth.backends.oidc import OIDCAuthBackend, OIDCConfig  # pylint: disable=C0415

        config = OIDCConfig(
            issuer=self.settings.OIDC_ISSUER,
            client_id=self.settings.OIDC_CLIENT_ID,
            client_secret=self.settings.OIDC_CLIENT_SECRET,
            redirect_uri=self.settings.OIDC_REDIRECT_URI,
        )

        return OIDCAuthBackend(
            app=self.app,
            config=config,
            user_service=self.users,
            session_service=self.sessions,
        )
