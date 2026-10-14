"""Backend without authentication or persistence.

.. classes::
    - `NoneAuthBackend`: Backend without authentication or persistence.

    
.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

import logging

from auth.backends.base import AuthBackend
from auth.models import User

LOGGER = logging.getLogger(__name__)

class NoneAuthBackend(AuthBackend):
    """Gives a virtual administrator identity.
    
    :param credentials: Dictionary containing 'username' and 'password'.
    :type credentials: dict[str, object] | None
    :return: Authenticated user.
    :rtype: User
    
    .. methods::
        - `authenticate`: Authenticate a user with given credentials.
        - `get_current_user`: Retrieve the current user based on session token.
        - `logout`: Logout the current session.

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """

    def authenticate(self, credentials: dict[str, object] | None = None) -> User:
        """Authenticate a user with given credentials.

        :param credentials: Dictionary containing 'username' and 'password'.
        :type credentials: dict[str, object] | None
        :return: Authenticated user.
        :rtype: User
        """
        del credentials
        LOGGER.debug("Authenticating with NoneAuthBackend")
        return self._local_user()

    def get_current_user(self, session_token: str | None = None) -> User:
        """Retrieve the current user based on session token.

        :param session_token: Session token of the current session.
        :type session_token: str | None
        :return: Current user.
        :rtype: User
        """
        del session_token
        LOGGER.debug("Retrieving current user with NoneAuthBackend")
        return self._local_user()

    def logout(self, session_token: str | None = None) -> None:
        """Logout the current session.

        :param session_token: Session token of the current session.
        :type session_token: str | None
        :return: None
        :rtype: None
        """
        del session_token
        LOGGER.debug("Logging out with NoneAuthBackend")

    @staticmethod
    def _local_user() -> User:
        """Return a virtual local administrator user.

        :return: Virtual local administrator user.
        :rtype: User
        """
        LOGGER.debug("Creating local virtual administrator user")
        return User(
            id="local",
            username="local",
            groups=["ADMIN"],
            auth_source="none",
        )
